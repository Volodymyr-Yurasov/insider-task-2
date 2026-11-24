from django.contrib import admin

from .models import LocationSubscription


@admin.register(LocationSubscription)
class LocationSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "location", "created_at", "updated_at")
    list_select_related = ("user", "location")
    raw_id_fields = ("user", "location")
    readonly_fields = ("created_at", "updated_at")
