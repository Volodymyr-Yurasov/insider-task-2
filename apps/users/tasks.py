from smtplib import SMTPException

from celery import shared_task
from django.contrib.auth import get_user_model

from apps.core.emails import send_templated_email

from .services import build_password_reset_url


@shared_task(
    autoretry_for=(SMTPException, OSError),
    retry_backoff=True,
    max_retries=5,
)
def send_password_reset_email(user_id: int) -> None:
    user = get_user_model().objects.filter(pk=user_id, is_active=True).first()
    if user is None:
        return
    send_templated_email(
        to=[user.email],
        subject="Reset your password",
        template="password_reset",
        context={"user": user, "reset_url": build_password_reset_url(user)},
    )
