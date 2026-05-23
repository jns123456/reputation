from django.contrib import admin

from comments.models import Comment, Vote


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("user", "market", "prediction", "popularity_score", "created_at")
    list_filter = ("market",)
    search_fields = ("body", "user__username", "market__title")


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ("user", "target_type", "target_id", "value", "created_at")
    list_filter = ("target_type", "value")
