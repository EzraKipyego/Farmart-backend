import logging
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from farmart.permissions import IsBuyer
from orders.models import Order

from .daraja import initiate_stk_push
from .models import Payment
from .phone_utils import normalize_phone_number

logger = logging.getLogger(__name__)


def error_response(message, code, status, details=None):
    return Response({"message": message, "code": code, "details": details or {}}, status=status)


class StkPushView(APIView):
    permission_classes = [IsBuyer]

    def post(self, request):
        order_id = request.data.get("order_id")
        try:
            phone = normalize_phone_number(request.data.get("phone", ""))
            requested_amount = Decimal(str(request.data.get("amount")))
            order = Order.objects.prefetch_related("items").get(id=order_id, buyer=request.user)
        except ValueError:
            return error_response("Invalid phone number or order ID", "INVALID_REQUEST", 400)
        except (InvalidOperation, TypeError):
            return error_response("Invalid payment amount", "INVALID_AMOUNT", 400)
        except Order.DoesNotExist:
            return error_response("Order not found", "ORDER_NOT_FOUND", 404)

        order_amount = sum((Decimal(str(item.price)) * item.quantity for item in order.items.all()), Decimal("0"))
        if requested_amount != order_amount:
            return error_response("Payment amount does not match the order total", "AMOUNT_MISMATCH", 400)
        if order.payment_status != "pending":
            return error_response("Order is not payable", "ORDER_NOT_PAYABLE", 409)

        try:
            checkout_request_id, merchant_request_id = initiate_stk_push(phone, requested_amount, str(order.id))
        except Exception as error:
            logger.error("[payments] STK push failed: %s", error)
            return error_response("Could not reach the payment provider, try again", "PAYMENT_PROVIDER_UNAVAILABLE", 502)

        payment = Payment.objects.create(
            order=order,
            checkout_request_id=checkout_request_id,
            merchant_request_id=merchant_request_id,
            phone=phone,
            amount=requested_amount,
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
            payment = Payment.objects.get(checkout_request_id=checkout_request_id, order__buyer=request.user)
        except Payment.DoesNotExist:
            return error_response("Payment not found", "PAYMENT_NOT_FOUND", 404)

        result = {"checkoutRequestId": payment.checkout_request_id, "status": payment.status}
        if payment.status == "success":
            result.update({"orderId": str(payment.order_id), "receipt": payment.mpesa_receipt_number})
        elif payment.status in ("failed", "cancelled", "timeout"):
            result["message"] = payment.result_description or "The payment request was not completed"
        return Response(result)


class DarajaCallbackView(APIView):
    permission_classes = [permissions.AllowAny]

    @transaction.atomic
    def post(self, request):
        try:
            callback = request.data["Body"]["stkCallback"]
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

        payment.result_code = str(result_code)
        payment.result_description = callback.get("ResultDesc", "")
        payment.completed_at = timezone.now()
        if result_code == 0:
            values = {item.get("Name"): item.get("Value") for item in callback.get("CallbackMetadata", {}).get("Item", [])}
            payment.status = "success"
            payment.mpesa_receipt_number = values.get("MpesaReceiptNumber")
            payment.phone = str(values.get("PhoneNumber") or payment.phone)
            payment.amount = Decimal(str(values.get("Amount") or payment.amount))
            payment.transaction_date = str(values.get("TransactionDate") or "")
            payment.order.payment_status = "success"
            payment.order.order_status = "processing"
            payment.order.save(update_fields=["payment_status", "order_status"])
        else:
            payment.status = "cancelled" if result_code == 1032 else "failed"
        payment.save()
        logger.info("[payments] Callback processed for %s: %s", checkout_request_id, payment.status)
        return Response({"message": "Callback received"}, status=200)
