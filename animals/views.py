from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions
from django.db.models import Q
from .models import Animal
from .serializers import AnimalSerializer
from farmart.permissions import IsFarmer


class AnimalListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsFarmer()]
        return [permissions.AllowAny()]

    def get(self, request):
        qs = Animal.objects.all()

        animal_type = request.query_params.get("type")
        breed = request.query_params.get("breed")
        search = request.query_params.get("search")
        min_age = request.query_params.get("min_age")
        max_age = request.query_params.get("max_age")
        min_price = request.query_params.get("min_price")
        max_price = request.query_params.get("max_price")

        if animal_type:
            qs = qs.filter(type=animal_type)
        if breed:
            qs = qs.filter(breed=breed)
        if search:
            qs = qs.filter(Q(type__icontains=search) | Q(breed__icontains=search) | Q(title__icontains=search))
        if min_age:
            qs = qs.filter(age__gte=float(min_age))
        if max_age:
            qs = qs.filter(age__lte=float(max_age))
        if min_price:
            qs = qs.filter(price__gte=float(min_price))
        if max_price:
            qs = qs.filter(price__lte=float(max_price))

        return Response(AnimalSerializer(qs, many=True).data)

    def post(self, request):
        required = ["type", "breed", "title", "age", "weight", "price", "location"]
        missing = [f for f in required if request.data.get(f) in (None, "")]
        if missing:
            return Response({"message": f"Missing required fields: {', '.join(missing)}"}, status=400)

        animal = Animal.objects.create(
            type=request.data["type"],
            breed=request.data["breed"],
            title=request.data["title"],
            age=request.data["age"],
            age_unit=request.data.get("ageUnit", "years"),
            weight=request.data["weight"],
            price=request.data["price"],
            location=request.data["location"],
            description=request.data.get("description", ""),
            image=request.data.get("image", ""),
            farmer=request.user,
        )
        return Response(AnimalSerializer(animal).data, status=201)


class AnimalDetailView(APIView):
    def get_permissions(self):
        if self.request.method == "GET":
            return [permissions.AllowAny()]
        return [IsFarmer()]

    def get_object(self, animal_id):
        try:
            return Animal.objects.get(id=animal_id)
        except Animal.DoesNotExist:
            return None

    def get(self, request, animal_id):
        animal = self.get_object(animal_id)
        if not animal:
            return Response({"message": "Animal not found"}, status=404)
        return Response(AnimalSerializer(animal).data)

    def put(self, request, animal_id):
        animal = self.get_object(animal_id)
        if not animal:
            return Response({"message": "Animal not found"}, status=404)
        if animal.farmer_id != request.user.id:
            return Response({"message": "You can only edit your own listings"}, status=403)

        field_map = [
            ("type", "type"), ("breed", "breed"), ("title", "title"), ("age", "age"),
            ("ageUnit", "age_unit"), ("weight", "weight"), ("price", "price"),
            ("location", "location"), ("description", "description"), ("image", "image"),
        ]
        for field, attr in field_map:
            if field in request.data:
                setattr(animal, attr, request.data[field])
        animal.save()
        return Response(AnimalSerializer(animal).data)

    def delete(self, request, animal_id):
        animal = self.get_object(animal_id)
        if not animal:
            return Response({"message": "Animal not found"}, status=404)
        if animal.farmer_id != request.user.id:
            return Response({"message": "You can only delete your own listings"}, status=403)
        animal.delete()
        return Response({"id": str(animal_id), "deleted": True})


class FarmerAnimalsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        farmer_id = request.query_params.get("farmer_id") or request.user.id
        qs = Animal.objects.filter(farmer_id=farmer_id)
        return Response(AnimalSerializer(qs, many=True).data)
