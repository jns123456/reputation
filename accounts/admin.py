from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib import admin

from accounts.models import (
    AIAgentProfile,
    Bookmark,
    Notification,
    NotificationPreference,
    User,
    UserCategoryStats,
    UserFollow,
    UserProfile,
)


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [UserProfileInline]
    list_display = (
        "username",
        "email",
        "display_name",
        "identity_mode",
        "is_verified",
        "onboarding_completed",
        "is_ai_agent",
        "is_staff",
    )
    list_filter = (
        "is_ai_agent",
        "identity_mode",
        "is_verified",
        "verification_requested",
        "onboarding_completed",
        "is_staff",
    )
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "Profile",
            {
                "fields": (
                    "display_name",
                    "identity_mode",
                    "is_verified",
                    "verification_requested",
                    "onboarding_completed",
                    "is_ai_agent",
                    "bio",
                )
            },
        ),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            "Profile",
            {
                "fields": (
                    "display_name",
                    "identity_mode",
                    "is_verified",
                    "verification_requested",
                    "onboarding_completed",
                    "is_ai_agent",
                    "bio",
                )
            },
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


@admin.register(UserFollow)
class UserFollowAdmin(admin.ModelAdmin):
    list_display = ("follower", "following", "created_at")
    search_fields = ("follower__username", "following__username")


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "notify_followed_predictions",
        "notify_new_follower",
        "notify_votes_received",
        "notify_prediction_resolved",
        "notify_in_app",
        "notify_email",
    )
    search_fields = ("user__username",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "recipient",
        "actor",
        "notification_type",
        "prediction",
        "read_at",
        "created_at",
    )
    list_filter = ("notification_type", "read_at")
    search_fields = ("recipient__username", "actor__username")


@admin.register(AIAgentProfile)
class AIAgentProfileAdmin(admin.ModelAdmin):
    list_display = ("agent_name", "user", "model_provider", "model_name", "is_verified_agent")
    list_filter = ("is_verified_agent", "model_provider")
    search_fields = ("agent_name", "user__username")
