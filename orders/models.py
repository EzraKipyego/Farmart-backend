import uuid
from django.db import models
from accounts.models import User
from animals.models import Animal


class Order(models.Model):
    ORDER_STATUS_CHOICES = [
        ("pending_payment", "Pending Payment"),
        ("processing", "Processing"),
        ("accepted", "Accepted"),
        ("dispatched", "Dispatched"),
        ("delivered", "Delivered"),
        ("cancelled", "Cancelled"),
    ]
    PAYMENT_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")

    delivery_name = models.CharField(max_length=120, blank=True, default="")
    delivery_phone = models.CharField(max_length=20, blank=True, default="")
    delivery_county = models.CharField(max_length=80, blank=True, default="")
    delivery_address = models.CharField(max_length=255, blank=True, default="")

    order_status = models.CharField(max_length=20, choices=ORDER_STATUS_CHOICES, default="pending_payment")
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default="pending")
    idempotency_key = models.CharField(max_length=255, unique=True, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def _overall_status(self, items):
        statuses = {i.status for i in items}
        if not statuses:
            return "pending"
        if statuses == {"confirmed"}:
            return "confirmed"
        if "pending" in statuses:
            return "pending"
        if statuses == {"rejected"}:
            return "rejected"
        return "pending"

    def to_buyer_dict(self):
        items = list(self.items.all())
        farmer_names = sorted({i.farmer_name for i in items})
        return {
            "id": str(self.id),
            "orderId": str(self.id),
            "status": self.order_status,
            "payment_status": self.payment_status,
            "items": [i.to_dict() for i in items],
            "total": sum(i.price * i.quantity for i in items),
            "currency": "KES",
            "delivery_details": {
                "name": self.delivery_name,
                "phone": self.delivery_phone,
                "county": self.delivery_county,
                "address": self.delivery_address,
            },
            "farmerName": ", ".join(farmer_names) if farmer_names else "",
            "createdAt": self.created_at.strftime("%Y-%m-%d") if self.created_at else None,
        }

    def to_farmer_dict(self, farmer_id):
        farmer_items = [i for i in self.items.all() if str(i.farmer_id) == str(farmer_id)]
        return {
            "id": str(self.id),
            "status": self.order_status,
            "payment_status": self.payment_status,
            "items": [i.to_dict() for i in farmer_items],
            "total": sum(i.price * i.quantity for i in farmer_items),
            "currency": "KES",
            "buyerName": self.buyer.name,
            "createdAt": self.created_at.strftime("%Y-%m-%d") if self.created_at else None,
        }


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    animal = models.ForeignKey(Animal, on_delete=models.SET_NULL, null=True, blank=True)

    farmer_id = models.UUIDField()
    farmer_name = models.CharField(max_length=120)

    title = models.CharField(max_length=160)
    price = models.FloatField()
    quantity = models.IntegerField(default=1)

    status = models.CharField(max_length=20, default="pending")  # pending | confirmed | rejected

    def to_dict(self):
        return {
            "animalId": str(self.animal_id) if self.animal_id else None,
            "title": self.title,
            "quantity": self.quantity,
            "price": self.price,
        }
