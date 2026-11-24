from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.locations.models import Location

from . import services
from .models import LocationSubscription
from .serializers import LocationSubscriptionSerializer


class LocationSubscriptionView(APIView):
    """Subscribe to / unsubscribe from email notifications about a location's new reviews."""

    permission_classes = [IsAuthenticated]

    def _get_location(self, location_pk) -> Location:
        return get_object_or_404(Location.objects.all(), pk=location_pk)

    @extend_schema(
        request=None,
        responses={
            201: LocationSubscriptionSerializer,
            400: OpenApiResponse(description="Already subscribed"),
        },
    )
    def post(self, request, location_pk):
        location = self._get_location(location_pk)
        try:
            subscription = services.subscribe(user=request.user, location=location)
        except services.AlreadySubscribedError as exc:
            raise ValidationError("You are already subscribed to this location.") from exc
        return Response(
            LocationSubscriptionSerializer(subscription).data, status=status.HTTP_201_CREATED
        )

    @extend_schema(
        request=None,
        responses={204: None, 404: OpenApiResponse(description="Not subscribed")},
    )
    def delete(self, request, location_pk):
        location = self._get_location(location_pk)
        if not services.unsubscribe(user=request.user, location=location):
            raise NotFound("You are not subscribed to this location.")
        return Response(status=status.HTTP_204_NO_CONTENT)


class MySubscriptionListView(generics.ListAPIView):
    """Locations the current user follows."""

    serializer_class = LocationSubscriptionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = []

    def get_queryset(self):
        return (
            LocationSubscription.objects.filter(
                user=self.request.user, location__deleted_at__isnull=True
            )
            .select_related("location")
            .order_by("-created_at")
        )
