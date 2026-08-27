from django.urls import path

from .views import AnimalDetailView, AnimalListCreateView, FarmerAnimalsView

urlpatterns = [
    path("animals", AnimalListCreateView.as_view()),
    path("animals/<uuid:animal_id>", AnimalDetailView.as_view()),
    path("farmer/animals", FarmerAnimalsView.as_view()),
]
