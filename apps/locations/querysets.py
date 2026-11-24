from django.apps import apps
from django.conf import settings
from django.db.models import (
    Avg,
    Count,
    ExpressionWrapper,
    F,
    FloatField,
    IntegerField,
    OuterRef,
    Subquery,
    Value,
)
from django.db.models.functions import Coalesce, Ln
from django.utils import timezone

from apps.core.models import AliveManager, SoftDeleteQuerySet

# popularity = rating * ln(1 + reviews_count) + VIEWS_WEIGHT * ln(1 + views_7d)
VIEWS_WEIGHT = 0.5


def _aggregate_subquery(queryset, aggregate, output_field):
    """Correlated scalar subquery: one aggregate per outer location row.

    Separate subqueries avoid the row multiplication (and wrong counts) a JOIN across two
    reverse relations (reviews x views) would cause.
    """
    return Subquery(
        queryset.filter(location=OuterRef("pk"))
        .order_by()
        .values("location")
        .annotate(value=aggregate)
        .values("value"),
        output_field=output_field,
    )


class LocationQuerySet(SoftDeleteQuerySet):
    # Bulk soft delete / restore use `update()`, which sends no `post_save` signal.
    def delete(self):
        from .cache import invalidate_location_list_cache

        result = super().delete()
        invalidate_location_list_cache()
        return result

    def restore(self):
        from .cache import invalidate_location_list_cache

        result = super().restore()
        invalidate_location_list_cache()
        return result

    def with_stats(self):
        """Annotate rating, reviews_count, views_7d and popularity. Nothing is stored."""
        review_model = apps.get_model("reviews", "Review")
        view_model = apps.get_model("locations", "LocationView")
        since = timezone.now() - settings.POPULARITY_VIEWS_WINDOW

        return self.annotate(
            rating=_aggregate_subquery(review_model.objects, Avg("rating"), FloatField()),
            reviews_count=Coalesce(
                _aggregate_subquery(review_model.objects, Count("pk"), IntegerField()), 0
            ),
            views_7d=Coalesce(
                _aggregate_subquery(
                    view_model.objects.filter(viewed_at__gte=since), Count("pk"), IntegerField()
                ),
                0,
            ),
        ).annotate(
            popularity=ExpressionWrapper(
                Coalesce(F("rating"), Value(0.0)) * Ln(Value(1.0) + F("reviews_count"))
                + Value(VIEWS_WEIGHT) * Ln(Value(1.0) + F("views_7d")),
                output_field=FloatField(),
            )
        )

    def with_relations(self):
        return self.select_related("category", "author")


class LocationManager(AliveManager.from_queryset(LocationQuerySet)):
    pass
