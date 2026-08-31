from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import IntegrityError
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import (
	PasswordResetConfirmSerializer,
	PasswordResetRequestSerializer,
	RegisterSerializer,
	UserSerializer,
)


def make_token(user):
	refresh = RefreshToken.for_user(user)
	refresh["role"] = user.role
	return str(refresh.access_token)


class RegisterView(APIView):
	permission_classes = [permissions.AllowAny]

	def post(self, request):
		email = (request.data.get("email") or "").strip().lower()
		role = request.data.get("role")
		if User.objects.filter(email=email, role=role).exists():
			return Response({"message": "An account with this email and role already exists."}, status=409)

		serializer = RegisterSerializer(data={**request.data, "email": email})
		if not serializer.is_valid():
			first_error = next(iter(serializer.errors.values()))[0]
			return Response({"message": str(first_error)}, status=400)

		try:
			user = serializer.save()
		except IntegrityError:
			return Response({"message": "An account with this email and role already exists."}, status=409)
		return Response(
			{"token": make_token(user), "user": UserSerializer(user).data, "message": "Account created successfully."},
			status=201,
		)


class LoginView(APIView):
	permission_classes = [permissions.AllowAny]

	def post(self, request):
		email = (request.data.get("email") or "").strip().lower()
		password = request.data.get("password") or ""
		role = request.data.get("role")
		if not email or not password or role not in ("farmer", "buyer"):
			return Response({"message": "Email, password, and account type are required"}, status=400)

		user = authenticate(request, email=email, password=password, role=role)
		if user is None:
			return Response({"message": "Incorrect email, password, or account type."}, status=401)
		return Response({"token": make_token(user), "user": UserSerializer(user).data})


class PasswordResetRequestView(APIView):
	permission_classes = [permissions.AllowAny]

	def post(self, request):
		serializer = PasswordResetRequestSerializer(data=request.data)
		if not serializer.is_valid():
			first_error = next(iter(serializer.errors.values()))[0]
			return Response({"message": str(first_error)}, status=400)

		email = serializer.validated_data["email"]
		role = serializer.validated_data["role"]
		user = User.objects.filter(email=email, role=role, is_active=True).first()
		if user:
			uid = urlsafe_base64_encode(force_bytes(user.pk))
			token = default_token_generator.make_token(user)
			reset_url = f"{settings.FRONTEND_ORIGIN.rstrip('/')}/reset-password?uid={uid}&token={token}"
			send_mail(
				"Farmart password reset",
				f"Use this link to reset your Farmart password:\n\n{reset_url}",
				settings.DEFAULT_FROM_EMAIL,
				[user.email],
			)

		return Response({"message": "Password reset email sent successfully."})


class PasswordResetConfirmView(APIView):
	permission_classes = [permissions.AllowAny]

	def post(self, request):
		serializer = PasswordResetConfirmSerializer(data=request.data)
		if not serializer.is_valid():
			first_error = next(iter(serializer.errors.values()))[0]
			return Response({"message": str(first_error)}, status=400)

		user = serializer.validated_data["user"]
		user.set_password(serializer.validated_data["password"])
		user.save(update_fields=["password"])
		return Response({"message": "Password changed successfully."})


class ProfileView(APIView):
	permission_classes = [permissions.IsAuthenticated]

	def get(self, request):
		return Response(UserSerializer(request.user).data)

	def put(self, request):
		user = request.user
		for field, attribute in (("name", "name"), ("phone", "phone"), ("county", "county"), ("farmName", "farm_name")):
			if field in request.data:
				setattr(user, attribute, request.data[field])
		user.save()
		return Response(UserSerializer(user).data)
