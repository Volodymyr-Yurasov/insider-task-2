from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower


class User(AbstractUser):
    """Custom user: unique (case-insensitive) email, required for password reset and emails.

    `date_joined` from AbstractUser serves as the creation timestamp.
    """

    email = models.EmailField("email address")
    updated_at = models.DateTimeField(auto_now=True)

    REQUIRED_FIELDS = ["email"]

    class Meta(AbstractUser.Meta):
        constraints = [
            models.UniqueConstraint(Lower("email"), name="users_user_email_ci_unique"),
        ]
