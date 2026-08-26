# //will com back later// from django.shortcuts import render

# Create your views here.
import re
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from .models import Payment
from .daraja import initiate_stk_push
from farmart.permissions import IsBuyer

logger = logging.getLogger(__name__)
PHONE_PATTERN = re.compile(r"^0[71]\d{8}$")


class StkPushView(APIView):
    permission_classes = [IsBuyer]

    def post(self, request):
        order_id = request.data.get("order_id")
        phone = request.data.get("phone", "")
        amount = request.data.get("amount")

        if not PHONE_PATTERN.match(phone):
            return Response({"message": "Enter a valid Safaricom number, e.g. 0712345678"}, status=400)
        if not amount or amount <= 0:
            return Response({"message": "Invalid payment amount"}, status=400)

        try:
            checkout_request_id, simulated = initiate_stk_push(phone, amount, order_id or "Farmart")
        except Exception as error:
            logger.error(f"[payments] STK push failed: {error}")
            return Response({"message": "Could not reach the payment provider, try again"}, status=502)

        payment = Payment.objects.create(
            order_id=order_id,
            checkout_request_id=checkout_request_id,
            phone=phone,
            amount=amount,
            # Simulated payments resolve immediately since there's no real Daraja
            # callback to wait for yet. Real payments stay "pending" until
            # /payments/callback receives Safaricom's webhook.
            status="success" if simulated else "pending",
        )
        return Response({"checkoutRequestId": checkout_request_id, "status": payment.status}, status=201)


class PaymentStatusView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, checkout_request_id):
        try:
            payment = Payment.objects.get(checkout_request_id=checkout_request_id)
        except Payment.DoesNotExist:
            return Response({"message": "Payment not found"}, status=404)
        return Response({"status": payment.status})


class DarajaCallbackView(APIView):
    """
    Safaricom posts here after the customer completes or cancels the STK
    push prompt on their phone. Body shape follows Daraja's documented
    STK callback format.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data = request.data
        logger.info(f"[payments] Daraja callback received: {data}")

        try:
            stk_callback = data["Body"]["stkCallback"]
            checkout_request_id = stk_callback["CheckoutRequestID"]
            result_code = stk_callback["ResultCode"]
        except (KeyError, TypeError):
            return Response({"message": "Malformed callback payload"}, status=400)

        try:
            payment = Payment.objects.get(checkout_request_id=checkout_request_id)
        except Payment.DoesNotExist:
            return Response({"message": "Unknown payment"}, status=404)

        if result_code == 0:
            payment.status = "success"
            items = stk_callback.get("CallbackMetadata", {}).get("Item", [])
            receipt_item = next((i for i in items if i.get("Name") == "MpesaReceiptNumber"), None)
            if receipt_item:
                payment.mpesa_receipt = receipt_item.get("Value")
        else:
            payment.status = "failed"

        payment.save()
        return Response({"message": "Callback received"})
