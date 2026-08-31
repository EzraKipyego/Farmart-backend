from django.urls import path

from .views import (
    LoginView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    ProfileView,
    RegisterView,
)

urlpatterns = [
    path("auth/register", RegisterView.as_view()),
    path("auth/login", LoginView.as_view()),
    path("auth/password-reset", PasswordResetRequestView.as_view()),
    path("auth/password-reset/confirm", PasswordResetConfirmView.as_view()),
    path("profile", ProfileView.as_view()),
]
