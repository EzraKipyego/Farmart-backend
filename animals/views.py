from django.db.models import Q
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView

from farmart.permissions import IsFarmer

from .models import Animal
from .serializers import AnimalSerializer


class AnimalListCreateView(APIView):
	def get_permissions(self):
		return [IsFarmer()] if self.request.method == "POST" else [permissions.AllowAny()]

	def get(self, request):
		queryset = Animal.objects.filter(available=True)
		if request.query_params.get("type"):
			queryset = queryset.filter(type=request.query_params["type"])
		if request.query_params.get("breed"):
			queryset = queryset.filter(breed=request.query_params["breed"])
		if request.query_params.get("search"):
			search = request.query_params["search"]
			queryset = queryset.filter(Q(type__icontains=search) | Q(breed__icontains=search) | Q(title__icontains=search))
		if request.query_params.get("min_age"):
			try:
				min_age = float(request.query_params["min_age"])
				queryset = queryset.filter(age__gte=min_age)
			except (TypeError, ValueError):
				pass
		if request.query_params.get("max_age"):
			try:
				max_age = float(request.query_params["max_age"])
				queryset = queryset.filter(age__lte=max_age)
			except (TypeError, ValueError):
				pass
		return Response(AnimalSerializer(queryset, many=True).data)

	def post(self, request):
		required = ["type", "breed", "title", "age", "weight", "price", "location"]
		missing = [field for field in required if request.data.get(field) in (None, "")]
		if missing:
			return Response({"message": f"Missing required fields: {', '.join(missing)}"}, status=400)
		animal = Animal.objects.create(
			type=request.data["type"], breed=request.data["breed"], title=request.data["title"],
			age=request.data["age"], age_unit=request.data.get("ageUnit", "years"),
			weight=request.data["weight"], price=request.data["price"], location=request.data["location"],
			description=request.data.get("description", ""), image=request.data.get("image", ""),
			farmer=request.user,
		)
		return Response(AnimalSerializer(animal).data, status=201)


class AnimalDetailView(APIView):
	def get_permissions(self):
		return [permissions.AllowAny()] if self.request.method == "GET" else [IsFarmer()]

	def get_object(self, animal_id):
		try:
			return Animal.objects.get(id=animal_id)
		except Animal.DoesNotExist:
			return None

	def get(self, request, animal_id):
		animal = self.get_object(animal_id)
		return Response(AnimalSerializer(animal).data) if animal else Response({"message": "Animal not found"}, status=404)

	def put(self, request, animal_id):
		animal = self.get_object(animal_id)
		if not animal:
			return Response({"message": "Animal not found"}, status=404)
		if animal.farmer_id != request.user.id:
			return Response({"message": "You can only edit your own listings"}, status=403)
		field_map = {"type": "type", "breed": "breed", "title": "title", "age": "age", "ageUnit": "age_unit", "weight": "weight", "price": "price", "location": "location", "description": "description", "image": "image", "available": "available"}
		for field, attribute in field_map.items():
			if field in request.data:
				setattr(animal, attribute, request.data[field])
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
		queryset = Animal.objects.filter(farmer_id=request.user.id)
		return Response(AnimalSerializer(queryset, many=True).data)
