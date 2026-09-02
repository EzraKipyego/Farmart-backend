from django.urls import path

from .views import BuyerOrdersView, CartView, CheckoutView, FarmerOrdersView, OrderStatusView

urlpatterns = [
    path("cart", CartView.as_view()),
    path("checkout", CheckoutView.as_view()),
    path("orders", BuyerOrdersView.as_view()),
    path("farmer/orders", FarmerOrdersView.as_view()),
    path("orders/<uuid:order_id>", OrderStatusView.as_view()),
]
