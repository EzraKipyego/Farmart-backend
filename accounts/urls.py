from django.urls import path

from .views import LoginView, ProfileView, RegisterView

urlpatterns = [
    path("auth/register", RegisterView.as_view()),
    path("auth/login", LoginView.as_view()),
    path("profile", ProfileView.as_view()),
]
