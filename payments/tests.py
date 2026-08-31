from unittest.mock import patch

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from animals.models import Animal
from orders.models import Order, OrderItem
from payments.models import Payment


class PaymentFlowTests(APITestCase):
    def setUp(self):
        self.buyer = User.objects.create_user("buyer@example.com", "Buyer", "password", role="buyer")
        self.farmer = User.objects.create_user("farmer@example.com", "Farmer", "password", role="farmer")
        self.animal = Animal.objects.create(
            farmer=self.farmer, type="Goat", breed="Dairy", title="Goat",
            age=2, weight=30, price=10000, location="Nakuru",
        )
        self.client.force_authenticate(self.buyer)

    def test_checkout_uses_server_price_and_starts_pending(self):
        response = self.client.post("/api/checkout", {
            "items": [{"animalId": str(self.animal.id), "quantity": 1, "price": 1}],
            "delivery_details": {"name": "Buyer", "phone": "0708319101"},
        }, format="json")
        self.assertEqual(response.status_code, 409)

        response = self.client.post("/api/checkout", {
            "items": [{"animalId": str(self.animal.id), "quantity": 1, "price": 10000}],
            "delivery_details": {"name": "Buyer", "phone": "0708319101"},
        }, format="json", HTTP_IDEMPOTENCY_KEY="checkout-1")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["status"], "pending_payment")
        self.assertEqual(response.data["subtotal"], "10000.00")
        self.assertEqual(response.data["delivery_fee"], "300.00")
        self.assertEqual(response.data["amount"], "10300.00")

    @patch("payments.views.initiate_stk_push", return_value=("ws_CO_test", "merchant_test"))
    def test_stk_is_pending_until_callback(self, _push):
        order = Order.objects.create(buyer=self.buyer, payment_status="pending", order_status="pending_payment")
        response = self.client.post("/api/payments/stk-push", {
            "order_id": str(order.id), "phone": "0708319101", "amount": 0,
        }, format="json")
        self.assertEqual(response.status_code, 400)

    def test_callback_marks_payment_and_order_success(self):
        order = Order.objects.create(buyer=self.buyer, payment_status="pending", order_status="pending_payment")
        payment = Payment.objects.create(
            order=order, checkout_request_id="ws_CO_callback", merchant_request_id="merchant_callback",
            phone="254708319101", amount=10000,
        )
        OrderItem.objects.create(
            order=order, animal=self.animal, farmer_id=self.farmer.id,
            farmer_name=self.farmer.name, title=self.animal.title, price=self.animal.price, quantity=1, status="pending",
        )
        response = self.client.post("/api/payments/callback", {
            "Body": {"stkCallback": {
                "CheckoutRequestID": payment.checkout_request_id, "ResultCode": 0,
                "ResultDesc": "The service request is processed successfully.",
                "CallbackMetadata": {"Item": [
                    {"Name": "MpesaReceiptNumber", "Value": "ABC123"},
                    {"Name": "Amount", "Value": 10000},
                    {"Name": "PhoneNumber", "Value": 254708319101},
                    {"Name": "TransactionDate", "Value": 20260827120000},
                ]},
            }}
        }, format="json")
        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        order.refresh_from_db()
        self.animal.refresh_from_db()
        self.assertEqual(payment.status, "success")
        self.assertEqual(order.payment_status, "success")
        self.assertEqual(order.order_status, "processing")
        self.assertFalse(self.animal.available)

    @patch("payments.views.query_stk_push_status", return_value={"status": "COMPLETED", "message": "Payment completed"})
    def test_pending_payment_status_endpoint_queries_daraja(self, mock_query):
        order = Order.objects.create(buyer=self.buyer, payment_status="pending", order_status="pending_payment")
        payment = Payment.objects.create(
            order=order, checkout_request_id="ws_CO_pending", merchant_request_id="merchant_pending",
            phone="254708319101", amount=10000, status="pending",
        )

        response = self.client.get(f"/api/payments/{payment.checkout_request_id}/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "COMPLETED")
        self.assertEqual(response.data["message"], "Payment completed")
        mock_query.assert_called_once_with(payment.checkout_request_id)
