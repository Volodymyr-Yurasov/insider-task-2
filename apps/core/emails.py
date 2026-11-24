from collections.abc import Sequence

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string


def send_templated_email(*, to: Sequence[str], subject: str, template: str, context: dict) -> None:
    """Render `emails/<template>.txt` and `.html` and send them as one multipart message."""
    text_body = render_to_string(f"emails/{template}.txt", context)
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=list(to),
    )
    message.attach_alternative(render_to_string(f"emails/{template}.html", context), "text/html")
    message.send()
