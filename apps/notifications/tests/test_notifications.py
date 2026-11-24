import pytest
from django.core import mail
from django.urls import reverse
from rest_framework import status

from apps.locations.tests.factories import LocationFactory
from apps.notifications.models import LocationSubscription
from apps.users.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def subscribe_url(location_pk):
    return reverse("notifications:location-subscribe", args=[location_pk])


def reviews_url(location_pk):
    return reverse("reviews:location-reviews", args=[location_pk])


MY_SUBSCRIPTIONS_URL = reverse("notifications:my-subscriptions")


@pytest.fixture
def owner():
    return UserFactory()


@pytest.fixture
def location(owner):
    return LocationFactory(author=owner)


class TestSubscriptionEndpoints:
    def test_subscribe(self, auth_client, user, location):
        response = auth_client.post(subscribe_url(location.id))

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["location"] == location.id
        assert LocationSubscription.objects.filter(user=user, location=location).exists()

    def test_second_subscribe_is_rejected(self, auth_client, location):
        auth_client.post(subscribe_url(location.id))

        response = auth_client.post(subscribe_url(location.id))

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert LocationSubscription.objects.count() == 1

    def test_unsubscribe(self, auth_client, location):
        auth_client.post(subscribe_url(location.id))

        assert auth_client.delete(subscribe_url(location.id)).status_code == 204
        assert not LocationSubscription.objects.exists()

    def test_unsubscribe_when_not_subscribed_is_404(self, auth_client, location):
        assert auth_client.delete(subscribe_url(location.id)).status_code == 404

    def test_requires_authentication(self, api_client, location):
        assert api_client.post(subscribe_url(location.id)).status_code == 403

    def test_cannot_subscribe_to_deleted_location(self, auth_client, location):
        location.delete()

        assert auth_client.post(subscribe_url(location.id)).status_code == 404

    def test_list_my_subscriptions(self, auth_client, other_client, location):
        auth_client.post(subscribe_url(location.id))
        other_client.post(subscribe_url(LocationFactory().id))

        response = auth_client.get(MY_SUBSCRIPTIONS_URL)

        assert [s["location"] for s in response.data["results"]] == [location.id]


class TestNewReviewEmails:
    def post_review(self, client, location, capture):
        with capture(execute=True):
            response = client.post(reviews_url(location.id), {"rating": 5, "comment": "Lovely"})
        assert response.status_code == status.HTTP_201_CREATED
        return response

    def test_location_author_is_emailed(
        self, auth_client, owner, location, django_capture_on_commit_callbacks
    ):
        self.post_review(auth_client, location, django_capture_on_commit_callbacks)

        assert len(mail.outbox) == 1
        message = mail.outbox[0]
        assert message.to == [owner.email]
        assert location.name in message.subject
        assert "Lovely" in message.body

    def test_subscribers_are_emailed_individually(
        self, auth_client, owner, location, django_capture_on_commit_callbacks
    ):
        subscribers = UserFactory.create_batch(2)
        for subscriber in subscribers:
            LocationSubscription.objects.create(user=subscriber, location=location)

        self.post_review(auth_client, location, django_capture_on_commit_callbacks)

        recipients = sorted(m.to[0] for m in mail.outbox)
        assert recipients == sorted([owner.email, *(s.email for s in subscribers)])
        assert all(len(m.to) == 1 for m in mail.outbox)

    def test_reviewer_is_not_notified_of_own_review(
        self, auth_client, user, location, django_capture_on_commit_callbacks
    ):
        LocationSubscription.objects.create(user=user, location=location)

        self.post_review(auth_client, location, django_capture_on_commit_callbacks)

        assert [m.to for m in mail.outbox] == [[location.author.email]]

    def test_subscribed_owner_gets_a_single_email(
        self, auth_client, owner, location, django_capture_on_commit_callbacks
    ):
        LocationSubscription.objects.create(user=owner, location=location)

        self.post_review(auth_client, location, django_capture_on_commit_callbacks)

        assert len(mail.outbox) == 1

    def test_editing_a_review_sends_nothing(
        self, auth_client, location, django_capture_on_commit_callbacks
    ):
        review_id = self.post_review(
            auth_client, location, django_capture_on_commit_callbacks
        ).data["id"]
        mail.outbox.clear()

        with django_capture_on_commit_callbacks(execute=True):
            auth_client.patch(reverse("reviews:review-detail", args=[review_id]), {"rating": 3})

        assert mail.outbox == []
