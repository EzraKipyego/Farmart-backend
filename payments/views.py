import logging
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from farmart.permissions import IsBuyer
from orders.models import Order

from .daraja import DarajaResponseError, initiate_stk_push, query_stk_push_status
from .models import Payment
from .phone_utils import normalize_phone_number


def _apply_payment_result(payment, result_code, result_description, metadata=None):
    metadata = metadata or {}
    payment.result_code = str(result_code)
    payment.result_description = result_description or ""
    payment.completed_at = timezone.now()

    if result_code == 0:
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
                item.animal.save(update_fields=["available"])
    else:
        payment.status = "cancelled" if result_code == 1032 else "failed"
        payment.order.payment_status = payment.status
        payment.order.save(update_fields=["payment_status"])

    payment.save()
    return payment

logger = logging.getLogger(__name__)


def error_response(message, code, status, details=None):
    return Response({"message": message, "code": code, "details": details or {}}, status=status)


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
            return error_response("Unable to send STK push", "DARaja_STK_REJECTED", 502, error.details)
        except Exception as error:
            logger.error("[payments] STK push failed: %s", error)
            return error_response("Could not reach the payment provider, try again", "PAYMENT_PROVIDER_UNAVAILABLE", 502)

        payment = Payment.objects.create(
            order=order,
            checkout_request_id=checkout_request_id,
            merchant_request_id=merchant_request_id,
            phone=phone,
            amount=order_amount,
            status="pending",
        )
        return Response({
            "checkoutRequestId": payment.checkout_request_id,
            "merchantRequestId": payment.merchant_request_id,
            "status": "pending",
            "message": "STK push sent",
        }, status=201)


class PaymentStatusView(APIView):
    permission_classes = [IsBuyer]

    def get(self, request, checkout_request_id):
        try:
            payment = Payment.objects.select_related("order").get(checkout_request_id=checkout_request_id, order__buyer=request.user)
        except Payment.DoesNotExist:
            return error_response("Payment not found", "PAYMENT_NOT_FOUND", 404)

        if payment.status == "pending":
            try:
                daraja_status = query_stk_push_status(payment.checkout_request_id)
            except Exception as exc:
                logger.warning("[payments] Daraja status query failed for %s: %s", payment.checkout_request_id, exc)
                return Response({
                    "checkoutRequestId": payment.checkout_request_id,
                    "status": "PENDING",
                    "message": "Payment verification is still pending; callback has not arrived yet.",
                }, status=200)

            status_name = daraja_status.get("status", "PENDING")
            message = daraja_status.get("message") or "Payment status query response"
            if status_name == "COMPLETED":
                metadata = (daraja_status.get("raw") or {}).get("CallbackMetadata") or {}
                _apply_payment_result(payment, 0, message, metadata)
            elif status_name == "FAILED":
                _apply_payment_result(payment, int(daraja_status.get("raw", {}).get("ResultCode", "1")) or 1, message, {})
            return Response({
                "checkoutRequestId": payment.checkout_request_id,
                "status": status_name,
                "message": message,
            }, status=200)

        result = {"checkoutRequestId": payment.checkout_request_id, "status": payment.status.upper() if payment.status else "PENDING"}
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


class DarajaCallbackView(APIView):
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        payload = request.data
        if isinstance(payload, dict) and "Body" in payload and isinstance(payload["Body"], dict):
            callback = payload["Body"].get("stkCallback")
        elif isinstance(payload, dict):
            callback = payload.get("stkCallback") or payload
        else:
            callback = None

        if not isinstance(callback, dict):
            return Response({"message": "Malformed callback payload"}, status=200)

        try:
            checkout_request_id = callback["CheckoutRequestID"]
            result_code = int(callback["ResultCode"])
        except (KeyError, TypeError, ValueError):
            return Response({"message": "Malformed callback payload"}, status=200)

        try:
            payment = Payment.objects.select_for_update().select_related("order").get(checkout_request_id=checkout_request_id)
        except Payment.DoesNotExist:
            logger.warning("[payments] Callback for unknown checkout request: %s", checkout_request_id)
            return Response({"message": "Callback received"}, status=200)

        if payment.status != "pending":
            return Response({"message": "Callback already processed"}, status=200)

        payment = _apply_payment_result(
            payment,
            result_code,
            callback.get("ResultDesc", ""),
            callback.get("CallbackMetadata", {}),
        )
        logger.info("[payments] Callback processed for %s: %s", checkout_request_id, payment.status)
        return Response({"message": "Callback received"}, status=200)
