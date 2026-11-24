from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.reviews.models import Review

from .tasks import notify_new_review


@receiver(post_save, sender=Review, dispatch_uid="notifications_new_review")
def queue_new_review_notifications(sender, instance, created, **kwargs):
    if created:
        # After commit: the worker must be able to read the review.
        transaction.on_commit(lambda: notify_new_review.delay(instance.pk))
