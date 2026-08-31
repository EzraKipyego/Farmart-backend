from django.urls import path

from .views import DarajaCallbackView, PaymentStatusView, StkPushView

urlpatterns = [
    path("payments/stk-push", StkPushView.as_view()),
    path("payments/status/<str:checkout_request_id>", PaymentStatusView.as_view()),
    path("payments/<str:checkout_request_id>/status", PaymentStatusView.as_view()),
    path("payments/callback", DarajaCallbackView.as_view()),
    path("payments/callback/", DarajaCallbackView.as_view()),
]
