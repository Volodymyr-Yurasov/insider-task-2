from django.conf import settings
from django.db import models

from apps.core.models import TimeStampedModel


class LocationSubscription(TimeStampedModel):
    """A user following a location to get emailed about its new reviews."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="location_subscriptions"
    )
    location = models.ForeignKey(
        "locations.Location", on_delete=models.CASCADE, related_name="subscriptions"
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "location"], name="subscription_one_per_user_per_location"
            ),
        ]

    def __str__(self):
        return f"{self.user_id} -> {self.location_id}"
