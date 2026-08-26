from django.urls import path
from .views import StkPushView, PaymentStatusView, DarajaCallbackView

urlpatterns = [
    path("payments/stk-push", StkPushView.as_view()),
    path("payments/<str:checkout_request_id>/status", PaymentStatusView.as_view()),
    path("payments/callback", DarajaCallbackView.as_view()),
]
