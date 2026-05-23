from django.contrib import admin

from reputation.models import PopularityEvent, ReputationEvent


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
