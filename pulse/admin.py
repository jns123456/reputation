from django.contrib import admin

from pulse.models import Comment, Poll, PollOption, PollVote, Post


class PollOptionInline(admin.TabularInline):
    model = PollOption
    extra = 0


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "ends_at", "created_at")
    list_filter = ("ends_at",)
    raw_id_fields = ("post",)
    inlines = [PollOptionInline]


@admin.register(PollVote)
class PollVoteAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "poll", "option", "updated_at")
    raw_id_fields = ("user", "poll", "option")


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
