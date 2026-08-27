import uuid
from django.db import models
from orders.models import Order


class Payment(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
        ("timeout", "Timeout"),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")
    checkout_request_id = models.CharField(max_length=80, unique=True)
    merchant_request_id = models.CharField(max_length=80, null=True, blank=True, unique=True)
    phone = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="KES")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    mpesa_receipt_number = models.CharField(max_length=80, null=True, blank=True, unique=True)
    result_code = models.CharField(max_length=10, null=True, blank=True)
    result_description = models.TextField(null=True, blank=True)
    transaction_date = models.CharField(max_length=20, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"Payment {self.checkout_request_id} - {self.status}"
