from django.db.models import F
from rest_framework.filters import OrderingFilter


class NullsLastOrderingFilter(OrderingFilter):
    """OrderingFilter that always puts NULLs last (e.g. unrated locations) and adds a
    `-pk` tie-breaker so pagination is stable."""

    def filter_queryset(self, request, queryset, view):
        ordering = self.get_ordering(request, queryset, view)
        if not ordering:
            return queryset
        expressions = [
            (
                F(field[1:]).desc(nulls_last=True)
                if field.startswith("-")
                else F(field).asc(nulls_last=True)
            )
            for field in ordering
        ]
        return queryset.order_by(*expressions, "-pk")
