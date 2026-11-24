from functools import cached_property

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.filters import OrderingFilter
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from apps.core.permissions import IsOwnerOrAdminOrReadOnly
from apps.locations.models import Location

from . import services
from .models import Review
from .serializers import ReviewSerializer, ReviewVoteSerializer, VoteInputSerializer


class LocationReviewListCreateView(generics.ListCreateAPIView):
    """Reviews of one location. One review per user per location; no self-reviews."""

    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly]
    filter_backends = [OrderingFilter]
    ordering_fields = ["created_at", "rating"]
    ordering = ["-created_at"]

    @cached_property
    def location(self) -> Location:
        # Default manager: soft-deleted locations 404.
        return get_object_or_404(Location.objects.all(), pk=self.kwargs["location_pk"])

    def get_queryset(self):
        return (
            Review.objects.filter(location=self.location)
            .select_related("author")
            .with_vote_counts()
        )

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if "location_pk" in self.kwargs:  # absent during schema generation
            context["location"] = self.location
        return context

    def perform_create(self, serializer):
        review = services.create_review(
            location=self.location, author=self.request.user, **serializer.validated_data
        )
        review.likes_count = review.dislikes_count = 0
        serializer.instance = review


class ReviewViewSet(
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """A single review: read by anyone, edited/deleted by its author or an admin."""

    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticatedOrReadOnly, IsOwnerOrAdminOrReadOnly]

    def get_queryset(self):
        return Review.objects.of_alive_locations().select_related("author").with_vote_counts()

    @extend_schema(
        methods=["PUT"],
        request=VoteInputSerializer,
        responses={
            201: ReviewVoteSerializer,
            200: ReviewVoteSerializer,
            400: OpenApiResponse(description="Invalid value or own review"),
        },
        description="Like (1) or dislike (-1). Creates the vote (201) or changes it (200).",
    )
    @extend_schema(
        methods=["DELETE"],
        request=None,
        responses={204: None, 404: OpenApiResponse(description="No vote to retract")},
        description="Retract your vote.",
    )
    @action(
        detail=True,
        methods=["put", "delete"],
        permission_classes=[IsAuthenticated],
        serializer_class=VoteInputSerializer,
    )
    def vote(self, request, pk=None):
        review = self.get_object()

        if request.method == "DELETE":
            if not services.retract_vote(review=review, user=request.user):
                raise NotFound("You have not voted on this review.")
            return Response(status=status.HTTP_204_NO_CONTENT)

        if review.author_id == request.user.id:
            raise ValidationError("You cannot vote on your own review.")
        serializer = VoteInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        vote, created = services.cast_vote(
            review=review, user=request.user, value=serializer.validated_data["value"]
        )
        return Response(
            ReviewVoteSerializer(vote).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
