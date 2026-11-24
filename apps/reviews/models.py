from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Count, Q

from apps.core.models import TimeStampedModel


class ReviewQuerySet(models.QuerySet):
    def of_alive_locations(self):
        return self.filter(location__deleted_at__isnull=True)

    def with_vote_counts(self):
        # A single reverse relation is joined, so plain filtered Counts are exact.
        return self.annotate(
            likes_count=Count("votes", filter=Q(votes__value=ReviewVote.Value.LIKE)),
            dislikes_count=Count("votes", filter=Q(votes__value=ReviewVote.Value.DISLIKE)),
        )


class Review(TimeStampedModel):
    MIN_RATING = 1
    MAX_RATING = 5

    location = models.ForeignKey(
        "locations.Location", on_delete=models.CASCADE, related_name="reviews"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(MIN_RATING), MaxValueValidator(MAX_RATING)]
    )
    comment = models.TextField()

    objects = ReviewQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["location", "author"],
                name="review_one_per_user_per_location",
                violation_error_message="You have already reviewed this location.",
            ),
            models.CheckConstraint(
                condition=Q(rating__gte=1) & Q(rating__lte=5),
                name="review_rating_range",
            ),
        ]

    def __str__(self):
        return f"{self.author_id} -> {self.location_id}: {self.rating}"


class ReviewVote(TimeStampedModel):
    """A user's single like/dislike on a review. Changing it updates the row in place;
    `created_at` is the first vote, `updated_at` the last change."""

    class Value(models.IntegerChoices):
        LIKE = 1, "Like"
        DISLIKE = -1, "Dislike"

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="votes")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="review_votes"
    )
    value = models.SmallIntegerField(choices=Value.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["review", "user"], name="vote_one_per_user_per_review"),
            models.CheckConstraint(condition=Q(value__in=[1, -1]), name="vote_value_valid"),
        ]

    def __str__(self):
        return f"{self.user_id} {self.get_value_display()} review {self.review_id}"
