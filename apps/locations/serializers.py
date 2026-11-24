from django.contrib.auth import get_user_model
from django.utils.text import slugify
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from apps.core.fields import RoundedFloatField

from .models import Category, Location


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ("id", "username")
        read_only_fields = fields


class CategorySerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(
        max_length=100,
        required=False,
        validators=[UniqueValidator(queryset=Category.objects.all())],
        help_text="Generated from the name when omitted.",
    )

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "is_active", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")

    def validate_name(self, value):
        queryset = Category.objects.filter(name__iexact=value)
        if self.instance is not None:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("A category with this name already exists.")
        return value

    def validate(self, attrs):
        if not attrs.get("slug") and "name" in attrs and self.instance is None:
            slug = slugify(attrs["name"])
            if not slug:
                raise serializers.ValidationError({"slug": "Cannot derive a slug; provide one."})
            if Category.objects.filter(slug=slug).exists():
                raise serializers.ValidationError({"slug": "Category with this slug exists."})
            attrs["slug"] = slug
        return attrs


class CategoryBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ("id", "name", "slug")
        read_only_fields = fields


class LocationSerializer(serializers.ModelSerializer):
    """Write `category` as an id; read it back nested via `category_detail`.

    Stats are ORM annotations from `LocationQuerySet.with_stats()`; they are never stored.
    """

    category = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.filter(is_active=True),
        error_messages={"does_not_exist": "Category does not exist or is inactive."},
    )
    category_detail = CategoryBriefSerializer(source="category", read_only=True)
    author = AuthorSerializer(read_only=True)
    rating = RoundedFloatField(read_only=True, allow_null=True)
    reviews_count = serializers.IntegerField(read_only=True)
    views_7d = serializers.IntegerField(read_only=True)
    popularity = RoundedFloatField(decimals=3, read_only=True)

    class Meta:
        model = Location
        fields = (
            "id",
            "name",
            "description",
            "category",
            "category_detail",
            "address",
            "latitude",
            "longitude",
            "author",
            "rating",
            "reviews_count",
            "views_7d",
            "popularity",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "author", "created_at", "updated_at")


class LocationExportQuerySerializer(serializers.Serializer):
    file_format = serializers.ChoiceField(choices=["csv", "json"], default="csv")
