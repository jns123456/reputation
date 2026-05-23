from django.contrib import admin

from markets.models import Market


@admin.register(Market)
class MarketAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "category", "source", "polymarket_synced_at", "kalshi_synced_at", "close_date")
    list_filter = ("status", "source", "category")
    search_fields = ("title", "external_id", "slug", "polymarket_slug", "kalshi_ticker")
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = (
        "created_at", "updated_at", "polymarket_synced_at", "kalshi_synced_at",
        "polymarket_raw", "polymarket_event_raw", "kalshi_raw", "kalshi_event_raw",
    )
    fieldsets = (
        (None, {"fields": ("title", "slug", "description", "category", "source", "status")}),
        ("Outcomes", {"fields": ("outcomes", "current_probability", "resolved_outcome")}),
        ("Polymarket", {"fields": ("external_id", "polymarket_slug", "polymarket_synced_at", "polymarket_raw", "polymarket_event_raw")}),
        ("Kalshi", {"fields": ("kalshi_ticker", "kalshi_synced_at", "kalshi_raw", "kalshi_event_raw")}),
        ("Dates", {"fields": ("close_date", "resolution_date", "created_at", "updated_at")}),
    )
