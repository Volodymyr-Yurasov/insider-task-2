import factory

from apps.locations.tests.factories import LocationFactory
from apps.reviews.models import Review, ReviewVote
from apps.users.tests.factories import UserFactory


class ReviewFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Review

    location = factory.SubFactory(LocationFactory)
    author = factory.SubFactory(UserFactory)
    rating = 4
    comment = "Worth a visit."


class ReviewVoteFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ReviewVote

    review = factory.SubFactory(ReviewFactory)
    user = factory.SubFactory(UserFactory)
    value = ReviewVote.Value.LIKE
