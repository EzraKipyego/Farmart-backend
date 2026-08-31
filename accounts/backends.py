from django.contrib.auth.backends import BaseBackend

from .models import User


class RoleEmailBackend(BaseBackend):
    """Authenticate a Farmart account by its email and selected role."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        email = (kwargs.get("email") or username or "").strip().lower()
        role = kwargs.get("role")
        if not email or not password or role not in ("farmer", "buyer"):
            return None

        try:
            user = User.objects.get(email=email, role=role)
        except User.DoesNotExist:
            return None

        return user if user.check_password(password) and self.user_can_authenticate(user) else None

    def user_can_authenticate(self, user):
        return getattr(user, "is_active", True)

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None
