import uuid
from django.db import models
from orders.models import Order


class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True)
    checkout_request_id = models.CharField(max_length=80, unique=True)
    phone = models.CharField(max_length=20)
    amount = models.FloatField()
    status = models.CharField(max_length=20, default="pending")  # pending | success | failed
    mpesa_receipt = models.CharField(max_length=80, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
