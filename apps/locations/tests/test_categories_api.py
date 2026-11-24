import pytest
from django.urls import reverse
from rest_framework import status

from apps.locations.models import Category

from .factories import CategoryFactory, LocationFactory

pytestmark = pytest.mark.django_db

LIST_URL = reverse("locations:category-list")


def detail_url(pk):
    return reverse("locations:category-detail", args=[pk])


class TestCategoryPermissions:
    def test_anyone_can_list_active_categories(self, api_client):
        active = CategoryFactory()
        CategoryFactory(is_active=False)

        response = api_client.get(LIST_URL)

        assert response.status_code == status.HTTP_200_OK
        assert [c["id"] for c in response.data["results"]] == [active.id]

    def test_admin_sees_inactive_categories(self, admin_client):
        CategoryFactory()
        CategoryFactory(is_active=False)

        response = admin_client.get(LIST_URL)

        assert response.data["count"] == 2

    @pytest.mark.parametrize("client_fixture", ["api_client", "auth_client"])
    def test_non_admin_cannot_create(self, request, client_fixture):
        client = request.getfixturevalue(client_fixture)

        response = client.post(LIST_URL, {"name": "Parks"})

        assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)
        assert not Category.objects.exists()


class TestCategoryAdminCrud:
    def test_create_generates_slug(self, admin_client):
        response = admin_client.post(LIST_URL, {"name": "Coffee Shops"})

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["slug"] == "coffee-shops"
        assert response.data["created_at"] and response.data["updated_at"]

    def test_name_is_unique_case_insensitive(self, admin_client):
        CategoryFactory(name="Parks")

        response = admin_client.post(LIST_URL, {"name": "parks", "slug": "parks-2"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data

    def test_update_bumps_updated_at_only(self, admin_client):
        category = CategoryFactory()
        created_at, updated_at = category.created_at, category.updated_at

        response = admin_client.patch(detail_url(category.id), {"is_active": False})

        assert response.status_code == status.HTTP_200_OK
        category.refresh_from_db()
        assert category.is_active is False
        assert category.created_at == created_at
        assert category.updated_at > updated_at

    def test_delete_unused_category(self, admin_client):
        category = CategoryFactory()

        response = admin_client.delete(detail_url(category.id))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Category.objects.filter(pk=category.pk).exists()

    def test_delete_category_in_use_conflicts(self, admin_client):
        location = LocationFactory()

        response = admin_client.delete(detail_url(location.category_id))

        assert response.status_code == status.HTTP_409_CONFLICT
        assert Category.objects.filter(pk=location.category_id).exists()
