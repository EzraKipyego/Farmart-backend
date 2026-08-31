import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, name, password=None, role="buyer", **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, name=name, role=role, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name, password=None, **extra_fields):
        extra_fields.setdefault("role", "farmer")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, name, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = (("farmer", "farmer"), ("buyer", "buyer"))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=120)
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    phone = models.CharField(max_length=20, blank=True, default="")
    county = models.CharField(max_length=80, blank=True, default="")
    farm_name = models.CharField(max_length=120, blank=True, default="")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    # Django requires USERNAME_FIELD to identify one account. Farmart login
    # deliberately uses email plus role through RoleEmailBackend instead.
    USERNAME_FIELD = "id"
    REQUIRED_FIELDS = ["email", "name"]

    def __str__(self):
        return f"{self.email} ({self.role})"

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["email", "role"], name="unique_email_role"),
        ]
