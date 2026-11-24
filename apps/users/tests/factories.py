import factory
from django.contrib.auth import get_user_model

DEFAULT_PASSWORD = "Str0ng-pass-123"


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = get_user_model()

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    password = factory.django.Password(DEFAULT_PASSWORD)
