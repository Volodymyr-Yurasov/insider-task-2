from django.urls import path

from .views import LocationSubscriptionView, MySubscriptionListView

app_name = "notifications"

urlpatterns = [
    path(
        "locations/<int:location_pk>/subscribe/",
        LocationSubscriptionView.as_view(),
        name="location-subscribe",
    ),
    path("subscriptions/", MySubscriptionListView.as_view(), name="my-subscriptions"),
]
