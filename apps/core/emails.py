from collections.abc import Iterable, Sequence

from django.conf import settings
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def build_templated_email(
    *, to: Sequence[str], subject: str, template: str, context: dict
) -> EmailMultiAlternatives:
    """Render `emails/<template>.txt` and `.html` into one multipart message."""
    message = EmailMultiAlternatives(
        subject=subject,
        body=render_to_string(f"emails/{template}.txt", context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=list(to),
    )
    message.attach_alternative(render_to_string(f"emails/{template}.html", context), "text/html")
    return message


def send_emails(messages: Iterable[EmailMultiAlternatives]) -> int:
    """Send several messages over a single connection of the default mailer."""
    messages = list(messages)
    if not messages:
        return 0
    with mail.mailers["default"] as connection:
        return connection.send_messages(messages) or 0


def send_templated_email(*, to: Sequence[str], subject: str, template: str, context: dict) -> None:
    send_emails([build_templated_email(to=to, subject=subject, template=template, context=context)])
