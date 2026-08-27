from django.shortcuts import render

# Create your views here.
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import RegisterSerializer, UserSerializer


def make_token(user):
	refresh = RefreshToken.for_user(user)
	refresh["role"] = user.role
	return str(refresh.access_token)


class RegisterView(APIView):
	permission_classes = [permissions.AllowAny]

	def post(self, request):
		email = (request.data.get("email") or "").strip().lower()
		if User.objects.filter(email=email).exists():
			return Response({"message": "An account with this email already exists"}, status=409)

		serializer = RegisterSerializer(data={**request.data, "email": email})
		if not serializer.is_valid():
			first_error = next(iter(serializer.errors.values()))[0]
			return Response({"message": str(first_error)}, status=400)

		user = serializer.save()
		return Response({"token": make_token(user), "user": UserSerializer(user).data}, status=201)


class LoginView(APIView):
	permission_classes = [permissions.AllowAny]

	def post(self, request):
		email = (request.data.get("email") or "").strip().lower()
		password = request.data.get("password") or ""
		if not email or not password:
			return Response({"message": "Email and password are required"}, status=400)

		try:
			user = User.objects.get(email=email)
		except User.DoesNotExist:
			return Response({"message": "Incorrect email or password"}, status=401)
		if not user.check_password(password):
			return Response({"message": "Incorrect email or password"}, status=401)
		return Response({"token": make_token(user), "user": UserSerializer(user).data})


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
