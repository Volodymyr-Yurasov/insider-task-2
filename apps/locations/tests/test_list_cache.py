import pytest
from django.urls import reverse

from apps.locations.models import Location
from apps.reviews.tests.factories import ReviewFactory

from .factories import CategoryFactory, LocationFactory

pytestmark = pytest.mark.django_db

LIST_URL = reverse("locations:location-list")


@pytest.fixture
def commit(django_capture_on_commit_callbacks):
    """Run on_commit callbacks (cache invalidation is deferred until commit)."""
    return lambda: django_capture_on_commit_callbacks(execute=True)


def test_second_request_is_served_from_cache(api_client, django_assert_num_queries):
    LocationFactory()
    first = api_client.get(LIST_URL)
    assert first["X-Cache"] == "MISS"

    with django_assert_num_queries(0):
        second = api_client.get(LIST_URL)

    assert second["X-Cache"] == "HIT"
    assert second.data == first.data


def test_different_query_params_are_cached_separately(api_client):
    LocationFactory()
    api_client.get(LIST_URL)

    assert api_client.get(LIST_URL, {"ordering": "created_at"})["X-Cache"] == "MISS"


def test_creating_location_invalidates(api_client, auth_client, commit):
    category = CategoryFactory()
    api_client.get(LIST_URL)

    with commit():
        auth_client.post(
            LIST_URL,
            {
                "name": "New",
                "category": category.id,
                "address": "Somewhere",
                "latitude": "1.0",
                "longitude": "2.0",
            },
        )

    response = api_client.get(LIST_URL)
    assert response["X-Cache"] == "MISS"
    assert response.data["count"] == 1


def test_updating_location_invalidates(api_client, commit):
    location = LocationFactory()
    api_client.get(LIST_URL)

    with commit():
        location.name = "Renamed"
        location.save()

    response = api_client.get(LIST_URL)
    assert response["X-Cache"] == "MISS"
    assert response.data["results"][0]["name"] == "Renamed"


def test_soft_deleting_location_invalidates(api_client, commit):
    location = LocationFactory()
    api_client.get(LIST_URL)

    with commit():
        location.delete()

    assert api_client.get(LIST_URL).data["count"] == 0


def test_bulk_soft_delete_invalidates(api_client, commit):
    LocationFactory.create_batch(2)
    api_client.get(LIST_URL)

    with commit():
        Location.objects.all().delete()

    assert api_client.get(LIST_URL).data["count"] == 0


def test_new_review_invalidates(api_client, commit):
    location = LocationFactory()
    assert api_client.get(LIST_URL).data["results"][0]["reviews_count"] == 0

    with commit():
        ReviewFactory(location=location, rating=5)

    response = api_client.get(LIST_URL)
    assert response["X-Cache"] == "MISS"
    assert response.data["results"][0]["reviews_count"] == 1
    assert response.data["results"][0]["rating"] == 5


def test_invalidation_waits_for_commit(api_client, django_capture_on_commit_callbacks):
    LocationFactory()
    api_client.get(LIST_URL)

    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        LocationFactory()

    # Not committed yet: readers keep getting the cached page.
    assert callbacks
    assert api_client.get(LIST_URL)["X-Cache"] == "HIT"
