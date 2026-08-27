import uuid
from django.db import models
from accounts.models import User


class Animal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(max_length=40)
    breed = models.CharField(max_length=80)
    title = models.CharField(max_length=160)
    age = models.FloatField()
    age_unit = models.CharField(max_length=20, default="years")
    weight = models.FloatField()
    price = models.FloatField()
    location = models.CharField(max_length=160)
    description = models.TextField(blank=True, default="")
    image = models.TextField(blank=True, default="")

    farmer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="animals")

    available = models.BooleanField(default=True)
    verified = models.BooleanField(default=False)
    vaccinated = models.BooleanField(default=False)
    health_certified = models.BooleanField(default=False)
    farmer_rating = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
