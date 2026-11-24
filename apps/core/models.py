from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """Abstract base adding `created_at` / `updated_at` to every mutable entity."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class SoftDeleteQuerySet(models.QuerySet):
    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def dead(self):
        return self.filter(deleted_at__isnull=False)

    def delete(self):
        """Bulk soft delete. `update()` bypasses `auto_now`, so `updated_at` is set explicitly."""
        now = timezone.now()
        return self.update(deleted_at=now, updated_at=now)

    def hard_delete(self):
        return super().delete()

    def restore(self):
        return self.update(deleted_at=None, updated_at=timezone.now())


class AliveManager(models.Manager.from_queryset(SoftDeleteQuerySet)):
    """Default manager: hides soft-deleted rows."""

    def get_queryset(self):
        return super().get_queryset().alive()


class SoftDeleteModel(TimeStampedModel):
    """Abstract base for soft-deletable entities.

    `objects` returns only live rows, `all_objects` returns everything (admin, restore).
    Related-object access (e.g. `review.location`) uses the unfiltered base manager, so
    reviews keep pointing at their location even after it is soft deleted.
    """

    deleted_at = models.DateTimeField(null=True, blank=True, editable=False)

    objects = AliveManager()
    all_objects = models.Manager.from_queryset(SoftDeleteQuerySet)()

    class Meta:
        abstract = True
        base_manager_name = "all_objects"

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def delete(self, using=None, keep_parents=False):
        self.deleted_at = timezone.now()
        self.save(update_fields=["deleted_at", "updated_at"])

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)

    def restore(self):
        self.deleted_at = None
        self.save(update_fields=["deleted_at", "updated_at"])
