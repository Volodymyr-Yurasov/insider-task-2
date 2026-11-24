from django.apps import AppConfig


class LocationsConfig(AppConfig):
    name = "apps.locations"
    label = "locations"

    def ready(self):
        from . import signals  # noqa: F401
