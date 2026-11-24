import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command

from apps.core.management.commands import seed
from apps.locations.models import Category, Location
from apps.locations.tests.factories import CategoryFactory
from apps.reviews.models import Review, ReviewVote
from apps.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

User = get_user_model()


def snapshot():
    return {
        "users": User.objects.count(),
        "categories": Category.objects.count(),
        "locations": Location.all_objects.count(),
        "reviews": Review.objects.count(),
        "votes": ReviewVote.objects.count(),
    }


def test_seed_creates_demo_data(django_capture_on_commit_callbacks):
    with django_capture_on_commit_callbacks(execute=True):
        call_command("seed")

    assert snapshot() == {
        "users": len(seed.USERS) + 1,
        "categories": len(seed.CATEGORIES),
        "locations": len(seed.LOCATIONS),
        "reviews": len(seed.REVIEWS),
        "votes": len(seed.VOTES),
    }
    admin = User.objects.get(username=seed.ADMIN_USERNAME)
    assert admin.is_superuser and admin.is_staff
    assert admin.check_password("Admin-pass-123")
    assert User.objects.get(username="olena").check_password("Demo-pass-123")
    # Bulk inserts bypass the new-review signal: seeding must not email anyone.
    assert mail.outbox == []


def test_seed_is_idempotent():
    call_command("seed")
    first = snapshot()

    call_command("seed")
    call_command("seed")

    assert snapshot() == first


def test_seed_never_overwrites_existing_rows():
    call_command("seed")
    admin = User.objects.get(username=seed.ADMIN_USERNAME)
    admin.set_password("Changed-pass-456")
    admin.save()
    location = Location.objects.get(name="Hydropark")
    location.delete()  # soft delete must not be undone or duplicated

    call_command("seed")

    admin.refresh_from_db()
    assert admin.check_password("Changed-pass-456")
    assert Location.all_objects.filter(name="Hydropark").count() == 1
    assert not Location.objects.filter(name="Hydropark").exists()


def test_seed_reuses_conflicting_existing_rows():
    """Rows created by hand with the same unique values must not cause IntegrityErrors."""
    CategoryFactory(name="parks", slug="custom-parks")
    UserFactory(username="someone", email="olena@example.com")

    call_command("seed")

    assert Category.objects.filter(name__iexact="parks").count() == 1
    assert User.objects.filter(email__iexact="olena@example.com").count() == 1


def test_seeded_data_is_visible_through_the_api(api_client):
    call_command("seed")

    response = api_client.get("/api/locations/", {"ordering": "-popularity"})

    assert response.data["count"] == len(seed.LOCATIONS)
    assert response.data["results"][0]["name"] == "Kyiv Pechersk Lavra"
