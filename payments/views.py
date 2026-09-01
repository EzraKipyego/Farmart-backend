import logging
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from farmart.permissions import IsBuyer
from orders.models import Order

from .daraja import DarajaGatewayError, DarajaResponseError, initiate_stk_push, query_stk_push_status
from .models import Payment
from .phone_utils import normalize_phone_number


def _apply_payment_result(payment, result_code, result_description, metadata=None):
    metadata = metadata or {}
    normalized_result_code = None
    try:
        normalized_result_code = int(str(result_code).strip())
    except (TypeError, ValueError):
        normalized_result_code = None

    payment.result_code = str(result_code)
    payment.result_description = result_description or ""
    payment.completed_at = timezone.now()

    if normalized_result_code == 0:
        values = {item.get("Name"): item.get("Value") for item in metadata.get("Item", []) if isinstance(item, dict)}
        payment.status = "success"
        payment.mpesa_receipt_number = values.get("MpesaReceiptNumber") or payment.mpesa_receipt_number
        payment.phone = str(values.get("PhoneNumber") or payment.phone)
        payment.amount = Decimal(str(values.get("Amount") or payment.amount))
        payment.transaction_date = str(values.get("TransactionDate") or payment.transaction_date or "")
        payment.order.payment_status = "success"
        payment.order.order_status = "processing"
        payment.order.save(update_fields=["payment_status", "order_status"])

        for item in payment.order.items.select_related("animal"):
            if item.animal_id:
                item.animal.available = False
                if hasattr(item.animal, "is_available"):
                    item.animal.is_available = False
                item.animal.save(update_fields=["available"])
    else:
        payment.status = "cancelled" if normalized_result_code == 1032 else "failed"
        payment.order.payment_status = payment.status
        payment.order.save(update_fields=["payment_status"])

    payment.save()
    return payment

logger = logging.getLogger(__name__)


def error_response(message, code, status, details=None):
    return Response({"message": message, "code": code, "details": details or {}}, status=status)


def persist_checkout_request_id(request, checkout_request_id, order_id=None):
    if not checkout_request_id:
        return
    request.session["pending_checkout_request_id"] = checkout_request_id
    if order_id:
        request.session["pending_checkout_order_id"] = str(order_id)


def get_persisted_checkout_request_id(request, checkout_request_id=None):
    if checkout_request_id:
        return checkout_request_id
    return request.GET.get("checkoutRequestId") or request.GET.get("checkout_request_id") or request.session.get("pending_checkout_request_id")


def _api_status_from_payment(payment_status):
    mapping = {
        "pending": "PENDING",
        "success": "COMPLETED",
        "failed": "FAILED",
        "cancelled": "FAILED",
        "timeout": "FAILED",
    }
    return mapping.get(payment_status, "PENDING")


class StkPushView(APIView):
    permission_classes = [IsBuyer]

    def post(self, request):
        order_id = request.data.get("order_id")
        try:
            phone = normalize_phone_number(request.data.get("phone") or request.data.get("phone_number", ""))
            order = Order.objects.prefetch_related("items").get(id=order_id, buyer=request.user)
        except ValueError:
            logger.warning("[payments] STK validation failed: invalid phone/order_id; fields=%s", list(request.data.keys()))
            return error_response("Invalid phone number or order ID", "INVALID_REQUEST", 400)
        except Order.DoesNotExist:
            logger.warning("[payments] STK validation failed: order not found; order_id=%s", order_id)
            return error_response("Order not found", "ORDER_NOT_FOUND", 404)

        order_amount = int(round(float(order.total)))
        if order_amount <= 0:
            logger.warning("[payments] STK validation failed: non-positive order total; order_id=%s", order_id)
            return error_response("Invalid payment amount", "INVALID_AMOUNT", 400)
        if order.payment_status in ("success",):
            return error_response("Order is not payable", "ORDER_NOT_PAYABLE", 409)

        active_payment = order.payments.filter(
            status="pending", created_at__gte=timezone.now() - timedelta(minutes=5)
        ).order_by("-created_at").first()
        if active_payment:
            return Response({
                "checkoutRequestId": active_payment.checkout_request_id,
                "merchantRequestId": active_payment.merchant_request_id,
                "status": "pending",
                "message": "STK push already in progress",
            }, status=200)

        try:
            checkout_request_id, merchant_request_id = initiate_stk_push(phone, order_amount, str(order.id))
        except DarajaResponseError as error:
            logger.error("[payments] Daraja rejected STK push: %s details=%s", error, error.details)
            return Response({"status": "FAILED", "message": "Unable to send STK push. Please try again."}, status=400)
        except DarajaGatewayError as error:
            logger.error("[payments] Daraja gateway error during STK push: %s details=%s", error, error.details)
            return Response({"status": "FAILED", "message": str(error) or "Payment gateway timeout. Please try again."}, status=getattr(error, "status_code", 504))
        except Exception as error:
            logger.error("[payments] STK push failed: %s", error)
            return Response({"status": "FAILED", "message": "Payment gateway unavailable. Please try again."}, status=504)

        payment = Payment.objects.create(
            order=order,
            checkout_request_id=checkout_request_id,
            merchant_request_id=merchant_request_id,
            phone=phone,
            amount=order_amount,
            status="pending",
        )
        persist_checkout_request_id(request, payment.checkout_request_id, str(order.id))
        return Response({
            "checkoutRequestId": payment.checkout_request_id,
            "merchantRequestId": payment.merchant_request_id,
            "status": "pending",
            "message": "STK push sent",
        }, status=201)


class PaymentStatusView(APIView):
    permission_classes = [IsBuyer]

    def get(self, request, checkout_request_id=None):
        checkout_request_id = get_persisted_checkout_request_id(request, checkout_request_id)
        if not checkout_request_id:
            return error_response("Payment not found", "PAYMENT_NOT_FOUND", 404)

        try:
            payment = Payment.objects.select_related("order").get(checkout_request_id=checkout_request_id, order__buyer=request.user)
        except Payment.DoesNotExist:
            return error_response("Payment not found", "PAYMENT_NOT_FOUND", 404)

        if payment.status == "pending":
            try:
                daraja_status = query_stk_push_status(payment.checkout_request_id)
            except DarajaGatewayError as exc:
                logger.warning("[payments] Daraja status query failed for %s: %s", payment.checkout_request_id, exc)
                return Response({
                    "checkoutRequestId": payment.checkout_request_id,
                    "status": "FAILED",
                    "message": str(exc) or "Payment gateway timeout. Please try again.",
                }, status=getattr(exc, "status_code", 504))
            except Exception as exc:
                logger.warning("[payments] Daraja status query failed for %s: %s", payment.checkout_request_id, exc)
                return Response({
                    "checkoutRequestId": payment.checkout_request_id,
                    "status": "FAILED",
                    "message": "Payment gateway timeout. Please try again.",
                }, status=504)

            status_name = daraja_status.get("status", "PENDING")
            message = daraja_status.get("message") or "Payment status query response"
            raw_result = daraja_status.get("raw") or {}
            if status_name == "COMPLETED":
                metadata = raw_result.get("CallbackMetadata") or raw_result.get("ResultMetadata") or {}
                _apply_payment_result(payment, 0, message, metadata)
            elif status_name == "FAILED":
                result_code = raw_result.get("ResultCode")
                try:
                    result_code_value = int(result_code) if result_code is not None else 1
                except (TypeError, ValueError):
                    result_code_value = 1
                _apply_payment_result(payment, result_code_value, message, raw_result)
            return Response({
                "checkoutRequestId": payment.checkout_request_id,
                "status": status_name,
                "message": message,
            }, status=200)

        result = {"checkoutRequestId": payment.checkout_request_id, "status": _api_status_from_payment(payment.status) if payment.status else "PENDING"}
        result.update({
            "subtotal": str(payment.order.subtotal),
            "delivery_fee": str(payment.order.delivery_fee),
            "amount": str(payment.order.total),
            "total": str(payment.order.total),
            "currency": payment.order.currency,
        })
        if payment.status == "success":
            result.update({"orderId": str(payment.order_id), "receipt": payment.mpesa_receipt_number})
            result["message"] = payment.result_description or "Payment completed successfully"
        elif payment.status in ("failed", "cancelled", "timeout"):
            result["message"] = payment.result_description or "The payment request was not completed"
        else:
            result["message"] = "Payment is pending confirmation"
        return Response(result)


@method_decorator(csrf_exempt, name='dispatch')
class DarajaCallbackView(APIView):
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        logger.info("[payments] Daraja callback received: method=%s path=%s headers=%s query=%s", request.method, request.path, dict(request.headers), dict(request.GET))
        raw_body = request.body.decode("utf-8", errors="replace") if request.body else ""
        logger.info("[payments] Daraja callback raw payload: %s", raw_body)

        payload = request.data
        if isinstance(payload, dict) and "Body" in payload and isinstance(payload["Body"], dict):
            callback = payload["Body"].get("stkCallback")
        elif isinstance(payload, dict):
            callback = payload.get("stkCallback") or payload
        else:
            callback = None

        if not isinstance(callback, dict):
            logger.warning("[payments] Malformed callback payload: %s", payload)
            return Response({"message": "Malformed callback payload"}, status=200)

        try:
            checkout_request_id = callback["CheckoutRequestID"]
            result_code_value = callback.get("ResultCode")
            if result_code_value is None:
                raise KeyError("ResultCode")
            result_code = int(str(result_code_value).strip())
        except (KeyError, TypeError, ValueError):
            logger.warning("[payments] Missing or invalid ResultCode/CheckoutRequestID in callback: %s", callback)
            return Response({"message": "Malformed callback payload"}, status=200)

        try:
            payment = Payment.objects.select_for_update().select_related("order").get(checkout_request_id=checkout_request_id)
        except Payment.DoesNotExist:
            logger.warning("[payments] Callback for unknown checkout request: %s", checkout_request_id)
            return Response({"message": "Callback received"}, status=200)

        if payment.status != "pending":
            return Response({"message": "Callback already processed"}, status=200)

        result_description = callback.get("ResultDesc") or "Daraja callback received"
        payment = _apply_payment_result(
            payment,
            result_code,
            result_description,
            callback.get("CallbackMetadata", {}),
        )
        logger.info("[payments] Callback processed for %s: %s | result_code=%s | result_desc=%s", checkout_request_id, payment.status, result_code, result_description)
        return Response({"message": "Callback received"}, status=200)
