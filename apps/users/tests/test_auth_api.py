import re
from urllib.parse import parse_qs, urlparse

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from .factories import DEFAULT_PASSWORD, UserFactory

pytestmark = pytest.mark.django_db

User = get_user_model()

REGISTER_URL = reverse("users:register")
LOGIN_URL = reverse("users:login")
LOGOUT_URL = reverse("users:logout")
ME_URL = reverse("users:me")
CSRF_URL = reverse("users:csrf")
RESET_URL = reverse("users:password-reset")
RESET_CONFIRM_URL = reverse("users:password-reset-confirm")


class TestRegister:
    def test_creates_user_with_normalized_email(self, api_client):
        payload = {"username": "alice", "email": "Alice@Example.COM", "password": DEFAULT_PASSWORD}

        response = api_client.post(REGISTER_URL, payload)

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["email"] == "alice@example.com"
        assert "password" not in response.data
        assert User.objects.get(username="alice").check_password(DEFAULT_PASSWORD)

    def test_rejects_duplicate_email_case_insensitive(self, api_client, user):
        payload = {"username": "new", "email": user.email.upper(), "password": DEFAULT_PASSWORD}

        response = api_client.post(REGISTER_URL, payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data

    def test_rejects_weak_password(self, api_client):
        payload = {"username": "bob", "email": "bob@example.com", "password": "123"}

        response = api_client.post(REGISTER_URL, payload)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "password" in response.data


class TestSessionAuth:
    def test_login_sets_session_cookie_and_me_works(self, api_client, user):
        response = api_client.post(
            LOGIN_URL, {"username": user.username, "password": DEFAULT_PASSWORD}
        )

        assert response.status_code == status.HTTP_200_OK
        assert "sessionid" in response.cookies
        me = api_client.get(ME_URL)
        assert me.status_code == status.HTTP_200_OK
        assert me.data["id"] == user.id

    def test_login_with_wrong_password_fails(self, api_client, user):
        response = api_client.post(LOGIN_URL, {"username": user.username, "password": "nope"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert api_client.get(ME_URL).status_code == status.HTTP_403_FORBIDDEN

    def test_logout_ends_session(self, auth_client):
        response = auth_client.post(LOGOUT_URL)

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert auth_client.get(ME_URL).status_code == status.HTTP_403_FORBIDDEN


class TestCsrf:
    def test_login_without_csrf_token_is_rejected(self, user):
        client = APIClient(enforce_csrf_checks=True)

        response = client.post(LOGIN_URL, {"username": user.username, "password": DEFAULT_PASSWORD})

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_login_with_csrf_token_succeeds(self, user):
        client = APIClient(enforce_csrf_checks=True)
        token = client.get(CSRF_URL).data["csrfToken"]

        response = client.post(
            LOGIN_URL,
            {"username": user.username, "password": DEFAULT_PASSWORD},
            headers={"X-CSRFToken": token},
        )

        assert response.status_code == status.HTTP_200_OK

    def test_authenticated_write_without_csrf_is_rejected(self, user):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(user)

        assert client.post(LOGOUT_URL).status_code == status.HTTP_403_FORBIDDEN


def _extract_link(body: str) -> str:
    return re.search(r"https?://\S+", body).group(0)


class TestPasswordReset:
    def _extract_uid_and_token(self, body: str) -> tuple[str, str]:
        query = parse_qs(urlparse(_extract_link(body)).query)
        return query["uid"][0], query["token"][0]

    def test_full_reset_flow_via_spa_and_api(
        self, api_client, user, settings, django_capture_on_commit_callbacks
    ):
        settings.FRONTEND_PASSWORD_RESET_URL = "https://app.example.com/reset-password"
        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(RESET_URL, {"email": user.email.upper()})

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [user.email]
        assert _extract_link(mail.outbox[0].body).startswith(
            "https://app.example.com/reset-password?uid="
        )
        uid, token = self._extract_uid_and_token(mail.outbox[0].body)

        new_password = "An0ther-str0ng-pass"
        response = api_client.post(
            RESET_CONFIRM_URL, {"uid": uid, "token": token, "new_password": new_password}
        )

        assert response.status_code == status.HTTP_200_OK
        user.refresh_from_db()
        assert user.check_password(new_password)

        # Token is single-use: the password hash changed, so the token is now invalid.
        response = api_client.post(
            RESET_CONFIRM_URL, {"uid": uid, "token": token, "new_password": "Yet-an0ther-pass"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_default_link_opens_backend_reset_page(
        self, api_client, user, settings, django_capture_on_commit_callbacks
    ):
        """Without an SPA configured, the emailed link works on its own."""
        settings.FRONTEND_PASSWORD_RESET_URL = ""
        settings.SITE_URL = "http://localhost:8000"
        with django_capture_on_commit_callbacks(execute=True):
            api_client.post(RESET_URL, {"email": user.email})
        link = _extract_link(mail.outbox[0].body)
        assert link.startswith("http://localhost:8000/accounts/reset/")

        browser = Client()
        # Django swaps the token from the URL into the session and redirects to a
        # token-free URL, so the token can't leak through the Referer header.
        form_page = browser.get(urlparse(link).path, follow=True)
        assert form_page.status_code == 200
        assert form_page.context["validlink"] is True
        set_password_url = form_page.redirect_chain[-1][0]

        new_password = "Fr0m-the-email-link"
        done = browser.post(
            set_password_url,
            {"new_password1": new_password, "new_password2": new_password},
            follow=True,
        )

        assert done.redirect_chain[-1][0] == reverse("password_reset_complete")
        user.refresh_from_db()
        assert user.check_password(new_password)
        # Single use: opening the same link again shows the "invalid link" page.
        reopened = Client().get(urlparse(link).path, follow=True)
        assert reopened.context["validlink"] is False

    def test_backend_reset_page_validates_password(
        self, user, settings, django_capture_on_commit_callbacks
    ):
        settings.FRONTEND_PASSWORD_RESET_URL = ""
        with django_capture_on_commit_callbacks(execute=True):
            Client().post(RESET_URL, {"email": user.email}, content_type="application/json")
        browser = Client()
        form_page = browser.get(urlparse(_extract_link(mail.outbox[0].body)).path, follow=True)

        response = browser.post(
            form_page.redirect_chain[-1][0], {"new_password1": "123", "new_password2": "123"}
        )

        assert response.status_code == 200
        assert response.context["form"].errors
        user.refresh_from_db()
        assert user.check_password(DEFAULT_PASSWORD)

    def test_unknown_email_returns_same_response_and_sends_nothing(
        self, api_client, django_capture_on_commit_callbacks
    ):
        with django_capture_on_commit_callbacks(execute=True):
            response = api_client.post(RESET_URL, {"email": "ghost@example.com"})

        assert response.status_code == status.HTTP_202_ACCEPTED
        assert mail.outbox == []

    def test_invalid_token_is_rejected(self, api_client):
        user = UserFactory()

        response = api_client.post(
            RESET_CONFIRM_URL, {"uid": "bad", "token": "bad", "new_password": "An0ther-str0ng"}
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        user.refresh_from_db()
        assert user.check_password(DEFAULT_PASSWORD)
