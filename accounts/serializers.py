from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    farmName = serializers.CharField(source="farm_name", required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ["id", "name", "email", "role", "phone", "county", "farmName"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ["name", "email", "password", "role", "phone", "county"]

    def validate_role(self, value):
        if value not in ("farmer", "buyer"):
            raise serializers.ValidationError("Role must be either farmer or buyer")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)
