import hashlib

from django.conf import settings
from django.core.cache import cache

from .models import Location, LocationView


def _viewer_id(request) -> str:
    if request.user.is_authenticated:
        return f"u:{request.user.pk}"
    # REMOTE_ADDR is only trustworthy without a proxy; behind one, a proxy-aware middleware
    # must set it from X-Forwarded-For. The IP is hashed so it never sits in Redis as-is.
    ip = request.META.get("REMOTE_ADDR", "")
    return "ip:" + hashlib.sha256(ip.encode()).hexdigest()[:16]


def register_view(*, location: Location, request) -> bool:
    """Count a detail view at most once per viewer per `LOCATION_VIEW_DEDUP_TTL`.

    `cache.add` is an atomic SET NX on Redis, so concurrent requests can't double-count.
    Returns whether the view was counted.
    """
    key = f"location-view:{location.pk}:{_viewer_id(request)}"
    if not cache.add(key, 1, timeout=settings.LOCATION_VIEW_DEDUP_TTL):
        return False
    LocationView.objects.create(
        location=location,
        user=request.user if request.user.is_authenticated else None,
    )
    return True
