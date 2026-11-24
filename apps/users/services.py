from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

User = get_user_model()


def normalize_email(email: str) -> str:
    return email.strip().lower()


def register_user(*, username: str, email: str, password: str) -> User:
    return User.objects.create_user(
        username=username, email=normalize_email(email), password=password
    )


def build_password_reset_url(user: User) -> str:
    """Link sent in the reset email.

    With `FRONTEND_PASSWORD_RESET_URL` set, it points at the SPA, which posts `uid` and
    `token` to the API's confirm endpoint. Otherwise it points at the backend's own reset
    page. Both share Django's token generator, so either can consume the token.
    """
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    if settings.FRONTEND_PASSWORD_RESET_URL:
        return f"{settings.FRONTEND_PASSWORD_RESET_URL}?{urlencode({'uid': uid, 'token': token})}"
    path = reverse("password_reset_confirm", kwargs={"uidb64": uid, "token": token})
    return f"{settings.SITE_URL.rstrip('/')}{path}"


def request_password_reset(*, email: str) -> None:
    """Queue reset emails for matching active users.

    Silent when nothing matches, so the endpoint can't be used to enumerate accounts.
    The token is generated inside the task, so it never travels through the broker.
    """
    from .tasks import send_password_reset_email

    user_ids = list(
        User.objects.filter(email__iexact=normalize_email(email), is_active=True).values_list(
            "pk", flat=True
        )
    )
    for user_id in user_ids:
        transaction.on_commit(lambda uid=user_id: send_password_reset_email.delay(uid))


def get_user_by_uidb64(uidb64: str) -> User | None:
    try:
        pk = force_str(urlsafe_base64_decode(uidb64))
        return User.objects.get(pk=pk, is_active=True)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None


def reset_password(*, user: User, new_password: str) -> None:
    # Changing the password rotates the session auth hash, logging out all other sessions.
    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])
