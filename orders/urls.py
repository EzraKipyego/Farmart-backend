from django.urls import path

from .views import BuyerOrdersView, CheckoutView, FarmerOrdersView, OrderStatusView

urlpatterns = [
    path("checkout", CheckoutView.as_view()),
    path("orders", BuyerOrdersView.as_view()),
    path("farmer/orders", FarmerOrdersView.as_view()),
    path("orders/<uuid:order_id>", OrderStatusView.as_view()),
]
