import pytest
from django.urls import reverse
from freezegun import freeze_time
from rest_framework import status

from apps.reviews.models import ReviewVote

from .factories import ReviewFactory, ReviewVoteFactory

pytestmark = pytest.mark.django_db

LIKE, DISLIKE = ReviewVote.Value.LIKE, ReviewVote.Value.DISLIKE


def vote_url(review_pk):
    return reverse("reviews:review-vote", args=[review_pk])


def review_url(pk):
    return reverse("reviews:review-detail", args=[pk])


@pytest.fixture
def review(other_user):
    return ReviewFactory(author=other_user)


class TestVote:
    def test_first_vote_creates(self, auth_client, user, review):
        response = auth_client.put(vote_url(review.id), {"value": LIKE})

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["value"] == LIKE
        assert ReviewVote.objects.get(review=review, user=user).value == LIKE

    def test_changing_vote_updates_in_place(self, auth_client, user, review):
        with freeze_time("2026-01-01 10:00"):
            auth_client.put(vote_url(review.id), {"value": LIKE})
        vote = ReviewVote.objects.get(review=review, user=user)

        with freeze_time("2026-01-01 11:00"):
            response = auth_client.put(vote_url(review.id), {"value": DISLIKE})

        assert response.status_code == status.HTTP_200_OK
        changed = ReviewVote.objects.get(review=review, user=user)
        assert changed.pk == vote.pk
        assert changed.value == DISLIKE
        assert changed.created_at == vote.created_at
        assert changed.updated_at > vote.updated_at

    def test_repeating_same_vote_is_a_noop(self, auth_client, user, review):
        auth_client.put(vote_url(review.id), {"value": LIKE})
        before = ReviewVote.objects.get(review=review, user=user)

        response = auth_client.put(vote_url(review.id), {"value": LIKE})

        assert response.status_code == status.HTTP_200_OK
        after = ReviewVote.objects.get(review=review, user=user)
        assert after.updated_at == before.updated_at
        assert ReviewVote.objects.filter(review=review, user=user).count() == 1

    @pytest.mark.parametrize("value", [0, 2, "like", None])
    def test_invalid_value_rejected(self, auth_client, review, value):
        response = auth_client.put(vote_url(review.id), {"value": value}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_vote_on_own_review(self, auth_client, user):
        own = ReviewFactory(author=user)

        response = auth_client.put(vote_url(own.id), {"value": LIKE})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not ReviewVote.objects.exists()

    def test_anonymous_cannot_vote(self, api_client, review):
        assert api_client.put(vote_url(review.id), {"value": LIKE}).status_code == 403

    def test_post_is_not_allowed(self, auth_client, review):
        response = auth_client.post(vote_url(review.id), {"value": LIKE})

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


class TestRetract:
    def test_delete_removes_vote(self, auth_client, user, review):
        ReviewVoteFactory(review=review, user=user)

        response = auth_client.delete(vote_url(review.id))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not ReviewVote.objects.exists()

    def test_delete_without_vote_is_404(self, auth_client, review):
        assert auth_client.delete(vote_url(review.id)).status_code == 404


class TestCounts:
    def test_review_exposes_like_and_dislike_counts(self, api_client, review):
        ReviewVoteFactory.create_batch(2, review=review, value=LIKE)
        ReviewVoteFactory(review=review, value=DISLIKE)

        response = api_client.get(review_url(review.id))

        assert response.data["likes_count"] == 2
        assert response.data["dislikes_count"] == 1

    def test_switching_vote_moves_count(self, auth_client, api_client, review):
        auth_client.put(vote_url(review.id), {"value": LIKE})
        auth_client.put(vote_url(review.id), {"value": DISLIKE})

        response = api_client.get(review_url(review.id))

        assert (response.data["likes_count"], response.data["dislikes_count"]) == (0, 1)
