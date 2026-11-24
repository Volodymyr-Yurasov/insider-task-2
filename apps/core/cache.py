"""Namespace-versioned response caching.

Every cached list response lives under `<namespace>:v<version>:<params-hash>`. Invalidation
bumps the namespace version, which makes all its entries unreachable in O(1) (no key scans);
stale entries simply expire via their TTL.
"""

import hashlib
import time

from django.core.cache import cache
from django.db import transaction
from rest_framework.response import Response


def _version_key(namespace: str) -> str:
    return f"{namespace}:version"


def get_namespace_version(namespace: str) -> int:
    key = _version_key(namespace)
    version = cache.get(key)
    if version is None:
        # Seed with a timestamp, so a lost version key never resurrects old entries.
        cache.add(key, time.time_ns(), timeout=None)
        version = cache.get(key)
    return version


def bump_namespace_version(namespace: str) -> None:
    key = _version_key(namespace)
    try:
        cache.incr(key)
    except ValueError:  # key missing (evicted / never set)
        cache.set(key, time.time_ns(), timeout=None)


def invalidate_on_commit(namespace: str) -> None:
    """Invalidate after the surrounding transaction commits, so readers never re-cache
    pre-commit data."""
    transaction.on_commit(lambda: bump_namespace_version(namespace))


class CachedListMixin:
    """Caches the `list` action of a viewset per unique query string.

    Responses must not depend on the requesting user, since all users share entries.
    """

    list_cache_namespace: str
    list_cache_timeout: int = 300

    def get_list_cache_key(self, request) -> str:
        params = sorted(request.query_params.lists())
        digest = hashlib.sha256(repr(params).encode()).hexdigest()[:32]
        version = get_namespace_version(self.list_cache_namespace)
        return f"{self.list_cache_namespace}:v{version}:{digest}"

    def list(self, request, *args, **kwargs):
        key = self.get_list_cache_key(request)
        data = cache.get(key)
        if data is not None:
            return Response(data, headers={"X-Cache": "HIT"})
        response = super().list(request, *args, **kwargs)
        if response.status_code == 200:
            cache.set(key, response.data, timeout=self.list_cache_timeout)
        response["X-Cache"] = "MISS"
        return response
