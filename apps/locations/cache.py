from apps.core.cache import invalidate_on_commit

LOCATION_LIST_CACHE_NAMESPACE = "locations:list"


def invalidate_location_list_cache() -> None:
    invalidate_on_commit(LOCATION_LIST_CACHE_NAMESPACE)
