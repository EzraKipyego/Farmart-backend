import re

from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers

from .models import User


PASSWORD_ERROR = "Password must be at least 6 characters and contain a letter, number, and special character."


def validate_new_password(value):
    if (
        len(value) < 6
        or not re.search(r"[A-Za-z]", value)
        or not re.search(r"\d", value)
        or not re.search(r"[^A-Za-z0-9]", value)
    ):
        raise serializers.ValidationError(PASSWORD_ERROR)
    return value


class UserSerializer(serializers.ModelSerializer):
    farmName = serializers.CharField(source="farm_name", required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ["id", "name", "email", "role", "phone", "county", "farmName"]


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_new_password])

    class Meta:
        model = User
        fields = ["name", "email", "password", "role", "phone", "county"]

    def validate_role(self, value):
        if value not in ("farmer", "buyer"):
            raise serializers.ValidationError("Role must be either farmer or buyer")
        return value

    def validate_email(self, value):
        return value.strip().lower()

    def create(self, validated_data):
        password = validated_data.pop("password")
        return User.objects.create_user(password=password, **validated_data)


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=User.ROLE_CHOICES)

    def validate_email(self, value):
        return value.strip().lower()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    password = serializers.CharField(write_only=True, validators=[validate_new_password])

    def validate(self, attrs):
        try:
            user_id = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=user_id)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            raise serializers.ValidationError({"token": "The password reset link is invalid or has expired."})

        if not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": "The password reset link is invalid or has expired."})

        attrs["user"] = user
        return attrs
