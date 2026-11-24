from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdminOrReadOnly(BasePermission):
    """Anyone may read; only staff may write."""

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


class IsOwnerOrAdminOrReadOnly(BasePermission):
    """Object-level: anyone may read; only the owner or staff may modify.

    The owner attribute defaults to `author`; override with `owner_field` on the view.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        if request.user.is_staff:
            return True
        owner_field = getattr(view, "owner_field", "author")
        return getattr(obj, f"{owner_field}_id", None) == request.user.id
