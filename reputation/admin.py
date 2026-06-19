from django.contrib import admin

from reputation.models import PopularityEvent, ReputationEvent, SeasonAward, WeeklyContestWinner


@admin.register(WeeklyContestWinner)
class WeeklyContestWinnerAdmin(admin.ModelAdmin):
    list_display = ("user", "week_code", "prize_type", "reputation_points", "prize_usd", "created_at")
    list_filter = ("week_code", "prize_type")
    search_fields = ("user__username",)
    readonly_fields = ("created_at",)


@admin.register(SeasonAward)
class SeasonAwardAdmin(admin.ModelAdmin):
    list_display = ("user", "season", "category_slug", "rank", "reputation_points", "created_at")
    list_filter = ("season",)
    search_fields = ("user__username",)
    readonly_fields = ("created_at",)


@admin.register(ReputationEvent)
class ReputationEventAdmin(admin.ModelAdmin):
    list_display = ("user", "event_type", "points_delta", "prediction", "created_at")
    list_filter = ("event_type",)
    search_fields = ("user__username", "reason")
    readonly_fields = ("created_at",)


@admin.register(PopularityEvent)
class PopularityEventAdmin(admin.ModelAdmin):
    list_display = ("user", "event_type", "points_delta", "comment", "created_at")
    list_filter = ("event_type",)
    search_fields = ("user__username", "reason")
    readonly_fields = ("created_at",)
