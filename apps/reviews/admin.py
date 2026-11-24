from django.contrib import admin

from .models import Review, ReviewVote


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("location", "author", "rating", "created_at", "updated_at")
    list_filter = ("rating",)
    search_fields = ("comment", "location__name", "author__username")
    list_select_related = ("location", "author")
    raw_id_fields = ("location", "author")
    readonly_fields = ("created_at", "updated_at")


@admin.register(ReviewVote)
class ReviewVoteAdmin(admin.ModelAdmin):
    list_display = ("review", "user", "value", "created_at", "updated_at")
    list_filter = ("value",)
    list_select_related = ("review", "user")
    raw_id_fields = ("review", "user")
    readonly_fields = ("created_at", "updated_at")
