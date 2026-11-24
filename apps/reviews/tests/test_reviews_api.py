import pytest
from django.urls import reverse
from rest_framework import status

from apps.locations.tests.factories import LocationFactory
from apps.reviews.models import Review

from .factories import ReviewFactory

pytestmark = pytest.mark.django_db


def location_reviews_url(location_pk):
    return reverse("reviews:location-reviews", args=[location_pk])


def review_url(pk):
    return reverse("reviews:review-detail", args=[pk])


@pytest.fixture
def location():
    return LocationFactory()


class TestCreateReview:
    def test_authenticated_user_can_review(self, auth_client, user, location):
        response = auth_client.post(
            location_reviews_url(location.id), {"rating": 5, "comment": "Great!"}
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["author"]["id"] == user.id
        assert response.data["location"] == location.id
        assert response.data["likes_count"] == 0
        assert response.data["created_at"] and response.data["updated_at"]

    def test_anonymous_cannot_review(self, api_client, location):
        response = api_client.post(location_reviews_url(location.id), {"rating": 5, "comment": "x"})

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_second_review_by_same_user_is_rejected(self, auth_client, user, location):
        ReviewFactory(location=location, author=user)

        response = auth_client.post(
            location_reviews_url(location.id), {"rating": 3, "comment": "Again"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "already reviewed" in str(response.data)
        assert Review.objects.filter(location=location, author=user).count() == 1

    @pytest.mark.parametrize("rating", [0, 6])
    def test_rating_must_be_between_1_and_5(self, auth_client, location, rating):
        response = auth_client.post(
            location_reviews_url(location.id), {"rating": rating, "comment": "x"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "rating" in response.data

    def test_comment_is_required(self, auth_client, location):
        response = auth_client.post(location_reviews_url(location.id), {"rating": 4})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "comment" in response.data

    def test_author_cannot_review_own_location(self, auth_client, user):
        own = LocationFactory(author=user)

        response = auth_client.post(location_reviews_url(own.id), {"rating": 5, "comment": "Me"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_review_deleted_location(self, auth_client, location):
        location.delete()

        response = auth_client.post(
            location_reviews_url(location.id), {"rating": 5, "comment": "x"}
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestReadReviews:
    def test_list_reviews_of_location(self, api_client, location):
        ReviewFactory.create_batch(2, location=location)
        ReviewFactory()  # another location

        response = api_client.get(location_reviews_url(location.id))

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2


class TestEditReview:
    def test_owner_can_edit(self, auth_client, user):
        review = ReviewFactory(author=user, rating=2)

        response = auth_client.patch(review_url(review.id), {"rating": 4})

        assert response.status_code == status.HTTP_200_OK
        review.refresh_from_db()
        assert review.rating == 4
        assert review.updated_at > review.created_at

    def test_location_cannot_be_changed(self, auth_client, user):
        review = ReviewFactory(author=user)
        other_location = LocationFactory()

        auth_client.patch(review_url(review.id), {"location": other_location.id})

        review.refresh_from_db()
        assert review.location_id != other_location.id

    def test_non_owner_cannot_edit_or_delete(self, other_client, user):
        review = ReviewFactory(author=user)

        assert other_client.patch(review_url(review.id), {"rating": 1}).status_code == 403
        assert other_client.delete(review_url(review.id)).status_code == 403

    def test_admin_can_delete(self, admin_client):
        review = ReviewFactory()

        assert admin_client.delete(review_url(review.id)).status_code == 204
        assert not Review.objects.filter(pk=review.pk).exists()
