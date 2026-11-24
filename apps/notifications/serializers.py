from rest_framework import serializers

from .models import LocationSubscription


class LocationSubscriptionSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)

    class Meta:
        model = LocationSubscription
        fields = ("id", "location", "location_name", "created_at", "updated_at")
        read_only_fields = fields
