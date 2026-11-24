import math
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time
from rest_framework.test import APIClient

from apps.locations.models import Location, LocationView
from apps.locations.querysets import VIEWS_WEIGHT
from apps.reviews.tests.factories import ReviewFactory

from .factories import LocationFactory, LocationViewFactory

pytestmark = pytest.mark.django_db


def detail_url(pk):
    return reverse("locations:location-detail", args=[pk])


def expected_popularity(rating, reviews, views):
    return (rating or 0) * math.log(1 + reviews) + VIEWS_WEIGHT * math.log(1 + views)


class TestComputedStats:
    def test_rating_and_counts_are_annotated_not_stored(self):
        location = LocationFactory()
        ReviewFactory(location=location, rating=5)
        ReviewFactory(location=location, rating=2)
        LocationViewFactory.create_batch(3, location=location)

        annotated = Location.objects.with_stats().get(pk=location.pk)

        assert annotated.rating == pytest.approx(3.5)
        assert annotated.reviews_count == 2
        assert annotated.views_7d == 3
        assert annotated.popularity == pytest.approx(expected_popularity(3.5, 2, 3))
        assert not hasattr(Location.objects.get(pk=location.pk), "rating")

    def test_views_older_than_seven_days_are_ignored(self):
        location = LocationFactory()
        LocationViewFactory(location=location, viewed_at=timezone.now() - timedelta(days=8))
        LocationViewFactory(location=location, viewed_at=timezone.now() - timedelta(days=6))

        assert Location.objects.with_stats().get(pk=location.pk).views_7d == 1

    def test_reviews_and_views_do_not_multiply_each_other(self):
        """Guards against the JOIN fan-out bug (reviews x views)."""
        location = LocationFactory()
        ReviewFactory.create_batch(3, location=location, rating=4)
        LocationViewFactory.create_batch(5, location=location)

        annotated = Location.objects.with_stats().get(pk=location.pk)

        assert (annotated.reviews_count, annotated.views_7d) == (3, 5)


class TestViewCounting:
    def test_detail_view_is_counted_once_per_hour_per_user(self, auth_client):
        location = LocationFactory()

        with freeze_time() as frozen:
            auth_client.get(detail_url(location.id))
            auth_client.get(detail_url(location.id))
            assert LocationView.objects.filter(location=location).count() == 1

            frozen.tick(timedelta(minutes=59))
            auth_client.get(detail_url(location.id))
            assert LocationView.objects.filter(location=location).count() == 1

            frozen.tick(timedelta(minutes=2))
            auth_client.get(detail_url(location.id))
            assert LocationView.objects.filter(location=location).count() == 2

    def test_anonymous_views_are_deduplicated_by_ip(self):
        location = LocationFactory()
        first, second = APIClient(), APIClient()

        first.get(detail_url(location.id), REMOTE_ADDR="10.0.0.1")
        second.get(detail_url(location.id), REMOTE_ADDR="10.0.0.1")
        second.get(detail_url(location.id), REMOTE_ADDR="10.0.0.2")

        assert LocationView.objects.filter(location=location).count() == 2

    def test_detail_response_includes_the_counted_view(self, auth_client, other_client):
        location = LocationFactory()

        assert auth_client.get(detail_url(location.id)).data["views_7d"] == 1
        assert auth_client.get(detail_url(location.id)).data["views_7d"] == 1
        assert other_client.get(detail_url(location.id)).data["views_7d"] == 2

    def test_view_is_attributed_to_user(self, auth_client, user):
        location = LocationFactory()

        auth_client.get(detail_url(location.id))

        assert LocationView.objects.get(location=location).user == user

    def test_list_does_not_count_views(self, api_client):
        LocationFactory()

        api_client.get(reverse("locations:location-list"))

        assert not LocationView.objects.exists()
