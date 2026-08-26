from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Order, OrderItem
from animals.models import Animal
from farmart.permissions import IsBuyer, IsFarmer


class CheckoutView(APIView):
    permission_classes = [IsBuyer]

    def post(self, request):
        items = request.data.get("items") or []
        delivery = request.data.get("delivery_details") or {}

        if not items:
            return Response({"message": "Your cart is empty"}, status=400)

        order = Order.objects.create(
            buyer=request.user,
            delivery_name=delivery.get("name", ""),
            delivery_phone=delivery.get("phone", ""),
            delivery_county=delivery.get("county", ""),
            delivery_address=delivery.get("address", ""),
        )

        for item in items:
            animal_id = item.get("animalId")
            animal = Animal.objects.filter(id=animal_id).first() if animal_id else None

            farmer_id = animal.farmer_id if animal else item.get("farmerId")
            farmer_name = animal.farmer.name if animal else item.get("farmerId", "Unknown farmer")

            OrderItem.objects.create(
                order=order,
                animal=animal,
                farmer_id=farmer_id,
                farmer_name=farmer_name,
                title=item.get("title", "Untitled listing"),
                price=item.get("price", 0),
                quantity=item.get("quantity", 1),
                status="pending",
            )

        return Response(order.to_buyer_dict(), status=201)


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

        new_status = request.data.get("status")
        if new_status not in ("confirmed", "rejected"):
            return Response({"message": "Status must be 'confirmed' or 'rejected'"}, status=400)

        farmer_items = order.items.filter(farmer_id=request.user.id)
        if not farmer_items.exists():
            return Response({"message": "You don't have any items in this order"}, status=403)

        farmer_items.update(status=new_status)
        return Response({"id": str(order.id), "status": new_status})
