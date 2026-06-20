from django.contrib import admin
from django.utils import timezone

from reputation.models import (
    ContestPayoutRequest,
    PopularityEvent,
    ReputationEvent,
    SeasonAward,
    WeeklyContestWinner,
)


@admin.register(WeeklyContestWinner)
class WeeklyContestWinnerAdmin(admin.ModelAdmin):
    list_display = ("user", "week_code", "prize_type", "reputation_points", "prize_usd", "notified_at", "created_at")
    list_filter = ("week_code", "prize_type")
    search_fields = ("user__username",)
    readonly_fields = ("created_at", "notified_at")


@admin.register(ContestPayoutRequest)
class ContestPayoutRequestAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "amount_usd",
        "chain",
        "status",
        "usdc_address",
        "created_at",
        "paid_at",
    )
    list_filter = ("status", "chain")
    search_fields = ("user__username", "usdc_address", "tx_hash")
    readonly_fields = ("created_at", "updated_at")
    actions = ("mark_paid", "mark_rejected")

    @admin.action(description="Mark selected as paid")
    def mark_paid(self, request, queryset):
        now = timezone.now()
        queryset.filter(status=ContestPayoutRequest.Status.PENDING).update(
            status=ContestPayoutRequest.Status.PAID,
            paid_at=now,
        )

    @admin.action(description="Mark selected as rejected")
    def mark_rejected(self, request, queryset):
        queryset.filter(status=ContestPayoutRequest.Status.PENDING).update(
            status=ContestPayoutRequest.Status.REJECTED,
        )


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
