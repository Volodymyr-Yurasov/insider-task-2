from rest_framework import serializers

from apps.locations.serializers import AuthorSerializer

from .models import Review, ReviewVote
from .services import DUPLICATE_REVIEW_MESSAGE


class ReviewSerializer(serializers.ModelSerializer):
    author = AuthorSerializer(read_only=True)
    likes_count = serializers.IntegerField(read_only=True)
    dislikes_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Review
        fields = (
            "id",
            "location",
            "author",
            "rating",
            "comment",
            "likes_count",
            "dislikes_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "location", "author", "created_at", "updated_at")

    def validate(self, attrs):
        if self.instance is None:  # creation: location comes from the URL, author from the session
            location = self.context["location"]
            user = self.context["request"].user
            if location.author_id == user.id:
                raise serializers.ValidationError("You cannot review your own location.")
            if Review.objects.filter(location=location, author=user).exists():
                raise serializers.ValidationError(DUPLICATE_REVIEW_MESSAGE)
        return attrs


class VoteInputSerializer(serializers.Serializer):
    value = serializers.ChoiceField(
        choices=ReviewVote.Value.choices, help_text="1 = like, -1 = dislike"
    )


class ReviewVoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewVote
        fields = ("review", "value", "created_at", "updated_at")
        read_only_fields = fields
