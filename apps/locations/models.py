from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone

from apps.core.models import SoftDeleteModel, TimeStampedModel

from .querysets import LocationManager, LocationQuerySet


class Category(TimeStampedModel):
    """Admin-managed set of location kinds. Deactivate instead of deleting when in use."""

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"
        constraints = [
            models.UniqueConstraint(Lower("name"), name="category_name_ci_unique"),
        ]

    def __str__(self):
        return self.name


class Location(SoftDeleteModel):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="locations")
    address = models.CharField(max_length=255)
    latitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    longitude = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="locations"
    )

    objects = LocationManager()
    all_objects = models.Manager.from_queryset(LocationQuerySet)()

    class Meta(SoftDeleteModel.Meta):
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(latitude__gte=-90) & Q(latitude__lte=90),
                name="location_latitude_range",
            ),
            models.CheckConstraint(
                condition=Q(longitude__gte=-180) & Q(longitude__lte=180),
                name="location_longitude_range",
            ),
        ]
        indexes = [
            models.Index(
                fields=["-created_at"],
                condition=Q(deleted_at__isnull=True),
                name="location_alive_created_idx",
            ),
            models.Index(fields=["latitude", "longitude"], name="location_coords_idx"),
        ]

    def __str__(self):
        return self.name


class LocationView(models.Model):
    """One counted detail view. An immutable event, so no `updated_at`.

    Raw events (instead of a stored counter) make the rolling 7-day window exact.
    """

    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name="views")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="location_views",
    )
    viewed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=["location", "viewed_at"], name="locationview_loc_time_idx"),
        ]

    def __str__(self):
        return f"{self.location_id} @ {self.viewed_at:%Y-%m-%d %H:%M}"
