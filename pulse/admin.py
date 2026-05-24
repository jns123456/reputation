from django.contrib import admin

from pulse.models import Comment, Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "body_preview", "popularity_score", "created_at")
    list_filter = ("created_at",)
    search_fields = ("body", "user__username")
    raw_id_fields = ("user",)

    @admin.display(description="Body")
    def body_preview(self, obj):
        return obj.body[:60] if obj.body else "(image)"


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "post", "body_preview", "popularity_score", "created_at")
    list_filter = ("created_at",)
    search_fields = ("body", "user__username")
    raw_id_fields = ("user", "post", "parent_comment")

    @admin.display(description="Body")
    def body_preview(self, obj):
        return obj.body[:60]
