from django.conf import settings
from django.db.models import ProtectedError
from django.http import HttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.core.cache import CachedListMixin
from apps.core.exceptions import Conflict
from apps.core.filters import NullsLastOrderingFilter
from apps.core.permissions import IsAdminOrReadOnly, IsOwnerOrAdminOrReadOnly

from .cache import LOCATION_LIST_CACHE_NAMESPACE
from .exporters import CONTENT_TYPES, export_locations
from .filters import CategoryFilter, LocationFilter
from .models import Category, Location
from .serializers import CategorySerializer, LocationExportQuerySerializer, LocationSerializer
from .services import register_view


class CategoryViewSet(viewsets.ModelViewSet):
    """Location categories. Readable by everyone, managed by admins only."""

    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    filterset_class = CategoryFilter
    search_fields = ["name"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        queryset = Category.objects.all()
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)
        return queryset

    @extend_schema(responses={204: None, 409: OpenApiResponse(description="Category in use")})
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError as exc:
            raise Conflict("Category is used by locations; deactivate it instead.") from exc


class LocationViewSet(CachedListMixin, viewsets.ModelViewSet):
    """Locations with computed `rating` and `popularity`.

    Anyone can read; authenticated users create; only the author or an admin can modify.
    `DELETE` is a soft delete. Opening a detail page counts a view (once per viewer per hour).
    """

    serializer_class = LocationSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwnerOrAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, SearchFilter, NullsLastOrderingFilter]
    filterset_class = LocationFilter
    search_fields = ["name", "description"]
    ordering_fields = ["created_at", "rating", "popularity"]
    ordering = ["-created_at"]
    list_cache_namespace = LOCATION_LIST_CACHE_NAMESPACE

    @property
    def list_cache_timeout(self):
        return settings.LOCATION_LIST_CACHE_TTL

    def get_queryset(self):
        return Location.objects.with_relations().with_stats()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        if register_view(location=instance, request=request):
            # Re-read so views_7d / popularity include the view just counted.
            instance = self.get_queryset().get(pk=instance.pk)
        return Response(self.get_serializer(instance).data)

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)
        self._reload_with_stats(serializer)

    def perform_update(self, serializer):
        serializer.save()
        self._reload_with_stats(serializer)

    def _reload_with_stats(self, serializer):
        """Saved instances lack the stats annotations the response needs."""
        serializer.instance = self.get_queryset().get(pk=serializer.instance.pk)

    @extend_schema(
        parameters=[LocationExportQuerySerializer],
        responses={
            (200, "text/csv"): OpenApiTypes.BINARY,
            (200, "application/json"): OpenApiTypes.BINARY,
        },
    )
    @action(detail=False, methods=["get"], url_path="export", pagination_class=None)
    def export(self, request):
        """Export the (filtered, searched, ordered) location list as CSV or JSON."""
        params = LocationExportQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        file_format = params.validated_data["file_format"]

        queryset = self.filter_queryset(self.get_queryset())
        response = HttpResponse(
            export_locations(queryset, file_format), content_type=CONTENT_TYPES[file_format]
        )
        filename = f"locations-{timezone.now():%Y%m%d-%H%M%S}.{file_format}"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
