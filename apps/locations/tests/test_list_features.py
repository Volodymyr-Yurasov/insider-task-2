from decimal import Decimal

import pytest
from django.urls import reverse

from apps.reviews.tests.factories import ReviewFactory
from apps.users.tests.factories import UserFactory

from .factories import CategoryFactory, LocationFactory, LocationViewFactory

pytestmark = pytest.mark.django_db

LIST_URL = reverse("locations:location-list")


def ids(response):
    return [item["id"] for item in response.data["results"]]


class TestSearch:
    def test_search_matches_name_and_description(self, api_client):
        by_name = LocationFactory(name="Botanical Garden", description="")
        by_description = LocationFactory(name="Park", description="old botanical trees")
        LocationFactory(name="Museum", description="art")

        response = api_client.get(LIST_URL, {"search": "botanical"})

        assert set(ids(response)) == {by_name.id, by_description.id}


class TestFilters:
    def test_filter_by_category_id_and_slug(self, api_client):
        cafes = CategoryFactory(slug="cafes")
        cafe = LocationFactory(category=cafes)
        LocationFactory()

        assert ids(api_client.get(LIST_URL, {"category": cafes.id})) == [cafe.id]
        assert ids(api_client.get(LIST_URL, {"category_slug": "cafes"})) == [cafe.id]

    def test_filter_by_author(self, api_client):
        author = UserFactory()
        mine = LocationFactory(author=author)
        LocationFactory()

        assert ids(api_client.get(LIST_URL, {"author": author.id})) == [mine.id]

    def test_filter_by_rating_range(self, api_client):
        great = LocationFactory()
        ReviewFactory(location=great, rating=5)
        ReviewFactory(location=great, rating=4)
        poor = LocationFactory()
        ReviewFactory(location=poor, rating=2)
        LocationFactory()  # unrated: excluded by any rating filter

        assert ids(api_client.get(LIST_URL, {"min_rating": 4})) == [great.id]
        assert ids(api_client.get(LIST_URL, {"max_rating": 3})) == [poor.id]

    def test_filter_by_bounding_box(self, api_client):
        kyiv = LocationFactory(latitude=Decimal("50.45"), longitude=Decimal("30.52"))
        LocationFactory(latitude=Decimal("49.84"), longitude=Decimal("24.03"))  # Lviv

        response = api_client.get(
            LIST_URL, {"min_lat": 50, "max_lat": 51, "min_lng": 30, "max_lng": 31}
        )

        assert ids(response) == [kyiv.id]

    def test_invalid_filter_value_returns_400(self, api_client):
        assert api_client.get(LIST_URL, {"min_rating": "abc"}).status_code == 400


class TestOrdering:
    def test_default_is_newest_first(self, api_client):
        old, new = LocationFactory(), LocationFactory()

        assert ids(api_client.get(LIST_URL)) == [new.id, old.id]

    def test_order_by_created_at_ascending(self, api_client):
        old, new = LocationFactory(), LocationFactory()

        assert ids(api_client.get(LIST_URL, {"ordering": "created_at"})) == [old.id, new.id]

    def test_order_by_rating_puts_unrated_last(self, api_client):
        unrated = LocationFactory()
        low = LocationFactory()
        ReviewFactory(location=low, rating=2)
        high = LocationFactory()
        ReviewFactory(location=high, rating=5)

        assert ids(api_client.get(LIST_URL, {"ordering": "-rating"})) == [
            high.id,
            low.id,
            unrated.id,
        ]
        assert ids(api_client.get(LIST_URL, {"ordering": "rating"})) == [
            low.id,
            high.id,
            unrated.id,
        ]

    def test_order_by_popularity(self, api_client):
        quiet = LocationFactory()
        viewed = LocationFactory()
        LocationViewFactory.create_batch(3, location=viewed)
        loved = LocationFactory()
        ReviewFactory.create_batch(3, location=loved, rating=5)

        assert ids(api_client.get(LIST_URL, {"ordering": "-popularity"})) == [
            loved.id,
            viewed.id,
            quiet.id,
        ]

    def test_unknown_ordering_field_is_ignored(self, api_client):
        LocationFactory()

        assert api_client.get(LIST_URL, {"ordering": "password"}).status_code == 200
