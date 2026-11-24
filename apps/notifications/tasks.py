from smtplib import SMTPException

from celery import shared_task

from . import services


@shared_task(
    autoretry_for=(SMTPException, OSError),
    retry_backoff=True,
    max_retries=5,
)
def notify_new_review(review_id: int) -> int:
    return services.notify_about_new_review(review_id)
