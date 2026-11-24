import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.users.tests.factories import UserFactory


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return UserFactory()


@pytest.fixture
def other_user(db):
    return UserFactory()


@pytest.fixture
def admin_user(db):
    return UserFactory(is_staff=True, is_superuser=True)


@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_login(user)
    return client


@pytest.fixture
def other_client(other_user):
    client = APIClient()
    client.force_login(other_user)
    return client


@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_login(admin_user)
    return client
