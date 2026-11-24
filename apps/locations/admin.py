from django.contrib import admin

from .models import Category, Location, LocationView


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")


class DeletedFilter(admin.SimpleListFilter):
    title = "deleted"
    parameter_name = "deleted"

    def lookups(self, request, model_admin):
        return (("no", "No"), ("yes", "Yes"))

    def queryset(self, request, queryset):
        if self.value() == "no":
            return queryset.alive()
        if self.value() == "yes":
            return queryset.dead()
        return queryset


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "author", "created_at", "updated_at", "deleted_at")
    list_filter = (DeletedFilter, "category")
    search_fields = ("name", "description", "address")
    list_select_related = ("category", "author")
    raw_id_fields = ("author",)
    readonly_fields = ("created_at", "updated_at", "deleted_at")
    actions = ("soft_delete_selected", "restore_selected")

    def get_queryset(self, request):
        # Admins see soft-deleted rows too, so they can restore them.
        return Location.all_objects.select_related("category", "author")

    def get_actions(self, request):
        actions = super().get_actions(request)
        # The stock bulk delete would show a misleading cascade confirmation.
        actions.pop("delete_selected", None)
        return actions

    @admin.action(description="Soft delete selected locations")
    def soft_delete_selected(self, request, queryset):
        count = queryset.alive().delete()
        self.message_user(request, f"Soft-deleted {count} location(s).")

    @admin.action(description="Restore selected locations")
    def restore_selected(self, request, queryset):
        count = queryset.dead().restore()
        self.message_user(request, f"Restored {count} location(s).")


@admin.register(LocationView)
class LocationViewAdmin(admin.ModelAdmin):
    list_display = ("location", "user", "viewed_at")
    list_select_related = ("location", "user")
    date_hierarchy = "viewed_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
