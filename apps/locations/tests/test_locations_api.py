import pytest
from django.urls import reverse
from rest_framework import status

from apps.locations.models import Location

from .factories import CategoryFactory, LocationFactory

pytestmark = pytest.mark.django_db

LIST_URL = reverse("locations:location-list")


def detail_url(pk):
    return reverse("locations:location-detail", args=[pk])


@pytest.fixture
def category():
    return CategoryFactory()


@pytest.fixture
def payload(category):
    return {
        "name": "Golden Gate",
        "description": "Historic gate",
        "category": category.id,
        "address": "Volodymyrska St, Kyiv",
        "latitude": "50.448853",
        "longitude": "30.513346",
    }


class TestCreate:
    def test_authenticated_user_creates_location_as_author(self, auth_client, user, payload):
        response = auth_client.post(LIST_URL, payload)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["author"] == {"id": user.id, "username": user.username}
        assert response.data["category_detail"]["id"] == payload["category"]
        assert response.data["rating"] is None
        assert response.data["reviews_count"] == 0
        assert response.data["popularity"] == 0
        assert response.data["created_at"] and response.data["updated_at"]

    def test_anonymous_cannot_create(self, api_client, payload):
        response = api_client.post(LIST_URL, payload)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert not Location.all_objects.exists()

    def test_author_cannot_be_spoofed(self, auth_client, user, other_user, payload):
        response = auth_client.post(LIST_URL, {**payload, "author": other_user.id})

        assert response.status_code == status.HTTP_201_CREATED
        assert Location.objects.get().author == user

    @pytest.mark.parametrize(("field", "value"), [("latitude", "90.5"), ("longitude", "-180.1")])
    def test_coordinates_out_of_range_rejected(self, auth_client, payload, field, value):
        response = auth_client.post(LIST_URL, {**payload, field: value})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert field in response.data

    def test_inactive_category_rejected(self, auth_client, payload):
        inactive = CategoryFactory(is_active=False)

        response = auth_client.post(LIST_URL, {**payload, "category": inactive.id})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "category" in response.data


class TestUpdateDelete:
    def test_owner_can_update(self, auth_client, user):
        location = LocationFactory(author=user)
        created_at = location.created_at

        response = auth_client.patch(detail_url(location.id), {"name": "Renamed"})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Renamed"
        assert "popularity" in response.data
        location.refresh_from_db()
        assert location.created_at == created_at
        assert location.updated_at > created_at

    def test_non_owner_cannot_update_or_delete(self, other_client, user):
        location = LocationFactory(author=user)

        assert other_client.patch(detail_url(location.id), {"name": "x"}).status_code == 403
        assert other_client.delete(detail_url(location.id)).status_code == 403

    def test_anonymous_cannot_update(self, api_client):
        location = LocationFactory()

        assert api_client.patch(detail_url(location.id), {"name": "x"}).status_code == 403

    def test_admin_can_update_any_location(self, admin_client):
        location = LocationFactory()

        response = admin_client.patch(detail_url(location.id), {"name": "By admin"})

        assert response.status_code == status.HTTP_200_OK

    def test_delete_is_soft(self, auth_client, user, api_client):
        location = LocationFactory(author=user)

        response = auth_client.delete(detail_url(location.id))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        stored = Location.all_objects.get(pk=location.pk)
        assert stored.deleted_at is not None
        assert stored.updated_at >= stored.deleted_at
        assert not Location.objects.filter(pk=location.pk).exists()
        assert api_client.get(detail_url(location.id)).status_code == status.HTTP_404_NOT_FOUND
        assert api_client.get(LIST_URL).data["count"] == 0

    def test_admin_can_delete_any_location(self, admin_client):
        location = LocationFactory()

        assert admin_client.delete(detail_url(location.id)).status_code == 204


class TestRead:
    def test_anonymous_can_read_list_and_detail(self, api_client):
        location = LocationFactory()

        assert api_client.get(LIST_URL).data["results"][0]["id"] == location.id
        assert api_client.get(detail_url(location.id)).data["name"] == location.name

    def test_list_is_paginated(self, api_client):
        LocationFactory.create_batch(3)

        response = api_client.get(LIST_URL, {"page_size": 2})

        assert response.data["count"] == 3
        assert len(response.data["results"]) == 2
        assert response.data["next"] is not None
