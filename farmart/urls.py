from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse


def health_check(request):
    return JsonResponse({"status": "ok", "service": "farmart-backend"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health", health_check),
    path("api/", include("accounts.urls")),
    path("api/", include("animals.urls")),
    path("api/", include("orders.urls")),
    path("api/", include("payments.urls")),
]
