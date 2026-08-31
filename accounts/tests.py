from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.test import TestCase, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from .models import User


class AuthenticationFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.email = "shared@example.com"

    def register(self, role, password="Password123!"):
        return self.client.post(
            "/api/auth/register",
            {
                "name": f"{role.title()} User",
                "email": self.email,
                "password": password,
                "role": role,
            },
            format="json",
        )

    def test_same_email_can_have_one_account_per_role(self):
        self.assertEqual(self.register("farmer").status_code, 201)
        self.assertEqual(self.register("buyer", "Buyer123!").status_code, 201)

        duplicate = self.register("farmer")
        self.assertEqual(duplicate.status_code, 409)
        self.assertEqual(duplicate.data["message"], "An account with this email and role already exists.")

        farmer_login = self.client.post(
            "/api/auth/login",
            {"email": self.email, "password": "Password123!", "role": "farmer"},
            format="json",
        )
        self.assertEqual(farmer_login.status_code, 200)
        self.assertEqual(farmer_login.data["user"]["role"], "farmer")
        self.assertEqual(AccessToken(farmer_login.data["token"])["role"], "farmer")

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {farmer_login.data['token']}")
        profile = self.client.get("/api/profile")
        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.data["role"], "farmer")
        self.client.credentials()

        self.assertEqual(
            authenticate(email=self.email, password="Password123!", role="farmer").role,
            "farmer",
        )
        self.assertIsNone(authenticate(email=self.email, password="Password123!", role="buyer"))

        wrong_role = self.client.post(
            "/api/auth/login",
            {"email": self.email, "password": "Password123!", "role": "buyer"},
            format="json",
        )
        self.assertEqual(wrong_role.status_code, 401)
        self.assertEqual(wrong_role.data["message"], "Incorrect email, password, or account type.")

        unknown_email = self.client.post(
            "/api/auth/login",
            {"email": "missing@example.com", "password": "Password123!", "role": "buyer"},
            format="json",
        )
        self.assertEqual(unknown_email.status_code, 401)
        self.assertEqual(unknown_email.data["message"], "Incorrect email, password, or account type.")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_password_reset_changes_password_without_affecting_login_policy(self):
        self.assertEqual(self.register("buyer").status_code, 201)
        user = User.objects.get(email=self.email, role="buyer")

        request_reset = self.client.post(
            "/api/auth/password-reset",
            {"email": self.email, "role": "buyer"},
            format="json",
        )
        self.assertEqual(request_reset.status_code, 200)
        self.assertEqual(request_reset.data["message"], "Password reset email sent successfully.")

        confirm = self.client.post(
            "/api/auth/password-reset/confirm",
            {
                "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                "token": default_token_generator.make_token(user),
                "password": "Updated123!",
            },
            format="json",
        )
        self.assertEqual(confirm.status_code, 200)

        old_login = self.client.post(
            "/api/auth/login",
            {"email": self.email, "password": "Password123!", "role": "buyer"},
            format="json",
        )
        self.assertEqual(old_login.status_code, 401)

        new_login = self.client.post(
            "/api/auth/login",
            {"email": self.email, "password": "Updated123!", "role": "buyer"},
            format="json",
        )
        self.assertEqual(new_login.status_code, 200)

    def test_registration_rejects_weak_password(self):
        response = self.register("buyer", "abcdef1")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["message"],
            "Password must be at least 6 characters and contain a letter, number, and special character.",
        )
