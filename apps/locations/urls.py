from rest_framework.routers import SimpleRouter

from .views import CategoryViewSet, LocationViewSet

app_name = "locations"

router = SimpleRouter()
router.register("categories", CategoryViewSet, basename="category")
router.register("locations", LocationViewSet, basename="location")

urlpatterns = router.urls
