from decimal import Decimal

import factory

from apps.locations.models import Category, Location, LocationView
from apps.users.tests.factories import UserFactory


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"Category {n}")
    slug = factory.Sequence(lambda n: f"category-{n}")


class LocationFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Location

    name = factory.Sequence(lambda n: f"Location {n}")
    description = "A nice place."
    category = factory.SubFactory(CategoryFactory)
    address = factory.Sequence(lambda n: f"{n} Main St, Kyiv")
    latitude = Decimal("50.450100")
    longitude = Decimal("30.523400")
    author = factory.SubFactory(UserFactory)


class LocationViewFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = LocationView

    location = factory.SubFactory(LocationFactory)
