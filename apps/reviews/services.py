from django.db import IntegrityError, transaction
from rest_framework.exceptions import ValidationError

from .models import Review, ReviewVote

DUPLICATE_REVIEW_MESSAGE = "You have already reviewed this location."


def create_review(*, location, author, rating: int, comment: str) -> Review:
    # The serializer pre-checks duplicates; the DB constraint closes the race window.
    try:
        with transaction.atomic():
            return Review.objects.create(
                location=location, author=author, rating=rating, comment=comment
            )
    except IntegrityError as exc:
        raise ValidationError({"non_field_errors": [DUPLICATE_REVIEW_MESSAGE]}) from exc


def cast_vote(*, review: Review, user, value: int) -> tuple[ReviewVote, bool]:
    """Create the user's vote or change it in place. Returns `(vote, created)`.

    Re-sending the same value is a no-op, so the call is idempotent.
    """
    vote, created = ReviewVote.objects.get_or_create(
        review=review, user=user, defaults={"value": value}
    )
    if not created and vote.value != value:
        vote.value = value
        vote.save(update_fields=["value", "updated_at"])
    return vote, created


def retract_vote(*, review: Review, user) -> bool:
    deleted, _ = ReviewVote.objects.filter(review=review, user=user).delete()
    return bool(deleted)
