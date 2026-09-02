from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Cart, Order, OrderItem
from animals.models import Animal
from farmart.permissions import IsBuyer, IsFarmer
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import logging
from django.db import transaction

logger = logging.getLogger(__name__)
MONEY_QUANTUM = Decimal("0.01")
DELIVERY_RATE = Decimal("0.03")


class CartView(APIView):
    permission_classes = [IsBuyer]

    def get(self, request):
        cart_items = Cart.objects.filter(user=request.user).select_related("animal")
        return Response([self.to_dict(item) for item in cart_items])

    def post(self, request):
        return self.save_item(request)

    def patch(self, request):
        return self.save_item(request)

    def delete(self, request):
        animal_id = request.data.get("animalId") or request.data.get("animal_id")
        if not animal_id:
            return Response({"message": "Missing animal ID", "code": "ANIMAL_ID_REQUIRED", "details": {}}, status=400)
        deleted, _ = Cart.objects.filter(user=request.user, animal_id=animal_id).delete()
        if not deleted:
            return Response({"message": "Cart item not found", "code": "CART_ITEM_NOT_FOUND", "details": {}}, status=404)
        return Response({"animalId": str(animal_id), "deleted": True})

    @staticmethod
    def to_dict(cart_item):
        animal = cart_item.animal
        return {
            "animalId": str(animal.id),
            "title": animal.title,
            "description": animal.description,
            "image": animal.image,
            "price": animal.price,
            "quantity": cart_item.quantity,
            "available": animal.available,
        }

    def save_item(self, request):
        animal_id = request.data.get("animalId") or request.data.get("animal_id")
        if not animal_id:
            return Response({"message": "Missing animal ID", "code": "ANIMAL_ID_REQUIRED", "details": {}}, status=400)
        try:
            quantity = int(request.data.get("quantity", 1))
        except (TypeError, ValueError):
            return Response({"message": "Quantity must be a positive integer", "code": "INVALID_QUANTITY", "details": {}}, status=400)
        if quantity < 1:
            return Response({"message": "Quantity must be a positive integer", "code": "INVALID_QUANTITY", "details": {}}, status=400)
        try:
            animal = Animal.objects.get(id=animal_id)
        except Animal.DoesNotExist:
            return Response({"message": "Animal not found", "code": "ANIMAL_NOT_FOUND", "details": {}}, status=404)
        if not animal.available:
            return Response({"message": "This animal is no longer available", "code": "ANIMAL_ALREADY_PURCHASED", "details": {"animalId": str(animal.id)}}, status=409)
        cart_item, created = Cart.objects.update_or_create(
            user=request.user,
            animal=animal,
            defaults={"quantity": quantity},
        )
        return Response(self.to_dict(cart_item), status=201 if created else 200)


class CheckoutView(APIView):
    permission_classes = [IsBuyer]

    def post(self, request):
        items = request.data.get("items") or []
        delivery = request.data.get("delivery_details") or {}
        idempotency_key = request.headers.get("Idempotency-Key") or request.data.get("idempotency_key")

        if not items:
            return Response({"message": "Your cart is empty"}, status=400)

        if idempotency_key:
            existing = Order.objects.filter(buyer=request.user, idempotency_key=idempotency_key).first()
            if existing:
                existing_total = existing.total.quantize(MONEY_QUANTUM)
                return Response({
                    "id": str(existing.id), "orderId": str(existing.id),
                    "status": existing.order_status,
                    "subtotal": str(existing.subtotal),
                    "delivery_fee": str(existing.delivery_fee),
                    "amount": str(existing_total), "total": str(existing_total),
                    "currency": existing.currency,
                }, status=201)

        # Validate all animals exist and get current prices
        subtotal = Decimal("0")
        order_items_data = []
        
        for item in items:
            animal_id = item.get("id") or item.get("animalId")
            try:
                quantity = int(item.get("quantity", 1))
            except (TypeError, ValueError):
                return Response({"message": "Quantity must be a positive integer"}, status=400)
            if quantity < 1:
                return Response({"message": "Quantity must be a positive integer"}, status=400)
            
            if not animal_id:
                return Response({"message": "Missing animal ID in cart item"}, status=400)
            
            try:
                animal = Animal.objects.select_related("farmer").get(id=animal_id)
            except Animal.DoesNotExist:
                return Response(
                    {"message": f"Animal {animal_id} no longer exists"},
                    status=404
                )
            
            if not animal.available:
                return Response({"message": f"Animal {animal_id} is no longer available"}, status=409)

            price = Decimal(str(animal.price))
            if item.get("price") is not None:
                try:
                    client_price = Decimal(str(item["price"]))
                except (InvalidOperation, TypeError):
                    return Response({"message": "Item price must be numeric"}, status=400)
                if client_price != price:
                    return Response({"message": f"The price for {animal.title} has changed"}, status=409)
            subtotal += price * quantity
            
            order_items_data.append({
                "animal": animal,
                "quantity": quantity,
                "price": price,
            })

        # Create order with status "pending_payment" - DO NOT mark as paid
        try:
            with transaction.atomic():
                order = Order.objects.create(
                    buyer=request.user,
                    delivery_name=delivery.get("name", ""),
                    delivery_phone=delivery.get("phone", ""),
                    delivery_county=delivery.get("county", ""),
                    delivery_address=delivery.get("address", ""),
                    subtotal=subtotal.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP),
                    delivery_fee=(subtotal * DELIVERY_RATE).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP),
                    total=(subtotal * (Decimal("1.00") + DELIVERY_RATE)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP),
                    currency="KES",
                    order_status="pending_payment",
                    payment_status="pending",
                    idempotency_key=idempotency_key,
                )

                for item_data in order_items_data:
                    animal = item_data["animal"]
                    OrderItem.objects.create(
                        order=order, animal=animal, farmer_id=animal.farmer_id,
                        farmer_name=animal.farmer.name, title=animal.title,
                        price=item_data["price"], quantity=item_data["quantity"], status="pending",
                    )
        except Exception as error:
            if idempotency_key and "unique constraint" in str(error).lower():
                order = Order.objects.get(buyer=request.user, idempotency_key=idempotency_key)
            else:
                raise

        return Response(
            {
                "id": str(order.id),
                "orderId": str(order.id),
                "status": "pending_payment",
                "subtotal": str(order.subtotal),
                "delivery_fee": str(order.delivery_fee),
                "amount": str(order.total),
                "total": str(order.total),
                "currency": order.currency,
            },
            status=201,
        )


class BuyerOrdersView(APIView):
    permission_classes = [IsBuyer]

    def get(self, request):
        orders = Order.objects.filter(buyer=request.user)
        return Response([o.to_buyer_dict() for o in orders])


class FarmerOrdersView(APIView):
    permission_classes = [IsFarmer]

    def get(self, request):
        orders = Order.objects.filter(items__farmer_id=request.user.id).distinct()
        return Response([o.to_farmer_dict(request.user.id) for o in orders])


class OrderStatusView(APIView):
    permission_classes = [IsFarmer]

    def patch(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id)
        except Order.DoesNotExist:
            return Response({"message": "Order not found"}, status=404)

        requested_status = str(request.data.get("status") or "").strip().lower()
        if requested_status in {"accept", "accepted", "confirmed"}:
            new_status = "accepted"
            response_status = "completed"
        elif requested_status in {"reject", "rejected", "cancelled"}:
            new_status = "cancelled"
            response_status = "rejected"
        else:
            new_status = requested_status
            response_status = requested_status

        if order.payment_status != "success":
            return Response({"message": "Unpaid orders cannot be processed", "code": "PAYMENT_REQUIRED", "details": {}}, status=409)

        if new_status not in ("processing", "accepted", "dispatched", "delivered", "cancelled"):
            return Response({"message": "Invalid order status", "code": "INVALID_STATUS", "details": {}}, status=400)

        farmer_items = order.items.filter(farmer_id=request.user.id)
        if not farmer_items.exists():
            return Response({"message": "You don't have any items in this order"}, status=403)

        farmer_items.update(status="confirmed" if new_status in ("processing", "accepted", "dispatched", "delivered") else "rejected")
        order.order_status = new_status
        order.save(update_fields=["order_status"])
        return Response({"id": str(order.id), "status": response_status, "payment_status": order.payment_status})
