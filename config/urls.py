from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

api_patterns = [
    path("auth/", include("apps.users.urls")),
    path("", include("apps.locations.urls")),
    path("", include("apps.reviews.urls")),
    path("", include("apps.notifications.urls")),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "docs/",
        # Custom template: keeps the CSRF header in sync with the cookie after login.
        SpectacularSwaggerView.as_view(url_name="schema", template_name="docs/swagger_ui.html"),
        name="docs",
    ),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include(api_patterns)),
]
