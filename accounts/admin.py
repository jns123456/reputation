from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib import admin

from accounts.models import AIAgentProfile, Bookmark, User, UserCategoryStats, UserProfile


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = ("username", "email", "display_name", "is_ai_agent", "is_staff")
    list_filter = ("is_ai_agent", "is_anonymous_profile", "is_staff")
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Profile",
            {
                "fields": (
                    "display_name",
                    "is_anonymous_profile",
                    "is_ai_agent",
                    "bio",
                )
            },
        ),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            "Profile",
            {"fields": ("display_name", "is_anonymous_profile", "is_ai_agent", "bio")},
        ),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "reputation_points",
        "popularity_points",
        "prediction_count",
        "reputation_score",
    )
    search_fields = ("user__username",)
    ordering = ("-reputation_score",)


@admin.register(UserCategoryStats)
class UserCategoryStatsAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "category_slug",
        "reputation_points",
        "popularity_points",
        "prediction_count",
    )
    list_filter = ("category_slug",)
    search_fields = ("user__username",)
    ordering = ("category_slug", "-reputation_score")


@admin.register(Bookmark)
class BookmarkAdmin(admin.ModelAdmin):
    list_display = ("user", "target_type", "target_id", "created_at")
    list_filter = ("target_type",)
    search_fields = ("user__username",)


@admin.register(AIAgentProfile)
class AIAgentProfileAdmin(admin.ModelAdmin):
    list_display = ("agent_name", "user", "model_provider", "model_name", "is_verified_agent")
    list_filter = ("is_verified_agent", "model_provider")
    search_fields = ("agent_name", "user__username")
