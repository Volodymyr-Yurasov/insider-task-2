import django_filters

from .models import Category, Location


class CategoryFilter(django_filters.FilterSet):
    class Meta:
        model = Category
        fields = ("is_active",)


class LocationFilter(django_filters.FilterSet):
    category = django_filters.NumberFilter(field_name="category_id")
    category_slug = django_filters.CharFilter(field_name="category__slug")
    author = django_filters.NumberFilter(field_name="author_id")
    # `rating` is an annotation from `with_stats()`; unrated locations (NULL) never match.
    min_rating = django_filters.NumberFilter(field_name="rating", lookup_expr="gte")
    max_rating = django_filters.NumberFilter(field_name="rating", lookup_expr="lte")
    # Map viewport (bounding box).
    min_lat = django_filters.NumberFilter(field_name="latitude", lookup_expr="gte")
    max_lat = django_filters.NumberFilter(field_name="latitude", lookup_expr="lte")
    min_lng = django_filters.NumberFilter(field_name="longitude", lookup_expr="gte")
    max_lng = django_filters.NumberFilter(field_name="longitude", lookup_expr="lte")

    class Meta:
        model = Location
        fields = (
            "category",
            "category_slug",
            "author",
            "min_rating",
            "max_rating",
            "min_lat",
            "max_lat",
            "min_lng",
            "max_lng",
        )
