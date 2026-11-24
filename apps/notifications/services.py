from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.db.models import Q

from apps.core.emails import build_templated_email, send_emails
from apps.reviews.models import Review

from .models import LocationSubscription


class AlreadySubscribedError(Exception):
    pass


def subscribe(*, user, location) -> LocationSubscription:
    try:
        with transaction.atomic():
            return LocationSubscription.objects.create(user=user, location=location)
    except IntegrityError as exc:
        raise AlreadySubscribedError from exc


def unsubscribe(*, user, location) -> bool:
    deleted, _ = LocationSubscription.objects.filter(user=user, location=location).delete()
    return bool(deleted)


def notify_about_new_review(review_id: int) -> int:
    """Email the location's author and its subscribers about a new review.

    Each recipient gets an individual message (no address leaks between recipients).
    The reviewer is never notified about their own review. Returns the number sent.
    """
    review = (
        Review.objects.select_related("author", "location__author")
        .filter(pk=review_id, location__deleted_at__isnull=True)
        .first()
    )
    if review is None:
        return 0
    location = review.location

    subscriber_ids = LocationSubscription.objects.filter(location=location).values("user_id")
    recipients = (
        get_user_model()
        .objects.filter(is_active=True)
        .filter(Q(pk__in=subscriber_ids) | Q(pk=location.author_id))
        .exclude(pk=review.author_id)
        .order_by("pk")
    )

    messages = []
    for recipient in recipients:
        if not recipient.email:
            continue
        is_owner = recipient.pk == location.author_id
        subject = (
            f"New review of your location “{location.name}”"
            if is_owner
            else f"New review of “{location.name}”"
        )
        messages.append(
            build_templated_email(
                to=[recipient.email],
                subject=subject,
                template="new_review",
                context={
                    "recipient": recipient,
                    "review": review,
                    "location": location,
                    "is_owner": is_owner,
                },
            )
        )
    return send_emails(messages)
