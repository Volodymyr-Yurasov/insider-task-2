from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import LocationReviewListCreateView, ReviewViewSet

app_name = "reviews"

router = SimpleRouter()
router.register("reviews", ReviewViewSet, basename="review")

urlpatterns = [
    path(
        "locations/<int:location_pk>/reviews/",
        LocationReviewListCreateView.as_view(),
        name="location-reviews",
    ),
    *router.urls,
]
