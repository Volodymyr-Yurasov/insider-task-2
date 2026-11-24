from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.locations.cache import invalidate_location_list_cache

from .models import Review


@receiver([post_save, post_delete], sender=Review, dispatch_uid="reviews_invalidate_locations")
def invalidate_location_list_on_review_change(sender, **kwargs):
    # Reviews change rating / reviews_count / popularity shown in the list.
    invalidate_location_list_cache()
