from rest_framework import serializers
from .models import Animal


class AnimalSerializer(serializers.ModelSerializer):
    ageUnit = serializers.CharField(source="age_unit", required=False)
    farmerId = serializers.CharField(source="farmer.id", read_only=True)
    farmerName = serializers.CharField(source="farmer.name", read_only=True)
    healthCertified = serializers.BooleanField(source="health_certified", required=False)
    farmerRating = serializers.FloatField(source="farmer_rating", read_only=True, allow_null=True)
    createdAt = serializers.SerializerMethodField()

    class Meta:
        model = Animal
        fields = [
            "id", "type", "breed", "title", "age", "ageUnit", "weight", "price", "location",
            "description", "image", "farmerId", "farmerName", "verified", "vaccinated",
            "healthCertified", "farmerRating", "createdAt",
        ]
        read_only_fields = ["id", "verified", "vaccinated", "farmerRating"]

    def get_createdAt(self, obj):
        return obj.created_at.strftime("%Y-%m-%d") if obj.created_at else None
