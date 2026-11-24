"""Keep the cached location list fresh.

Signals (rather than calls in views) also catch writes made through the admin or shell.
Soft delete is a `save()`, so `post_save` covers it.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .cache import invalidate_location_list_cache
from .models import Category, Location


@receiver([post_save, post_delete], sender=Location, dispatch_uid="locations_invalidate_loc")
@receiver([post_save, post_delete], sender=Category, dispatch_uid="locations_invalidate_cat")
def invalidate_list_on_location_change(sender, **kwargs):
    invalidate_location_list_cache()
