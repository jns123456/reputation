"""Shared source filter helpers for Polymarket / Kalshi browse UI."""

from urllib.parse import urlencode

from django.conf import settings

from markets.models import Market

VALID_MARKET_SOURCES = frozenset({Market.Source.POLYMARKET, Market.Source.KALSHI})


def kalshi_enabled() -> bool:
    return getattr(settings, "KALSHI_ENABLED", False)


def normalize_source_filter(value: str) -> str:
    value = (value or "").strip()
    if value == Market.Source.KALSHI and not kalshi_enabled():
        return ""
    if value in VALID_MARKET_SOURCES:
        return value
    return ""


def build_browse_clear_search_url(*, base_url: str, source: str = "", area: str = "") -> str:
    """Same browse page without an active search query."""
    params = {}
    if area:
        params["area"] = area
    if source:
        params["source"] = source
    query = urlencode(params)
    return f"{base_url}?{query}" if query else base_url


def build_source_filter_urls(*, base_url: str, active_source: str = "", extra: dict | None = None) -> dict:
    """Build All / Polymarket / Kalshi URLs preserving other query params."""
    extra = extra or {}
    base_params = {key: value for key, value in extra.items() if value}

    def url_for(source: str = "") -> str:
        params = dict(base_params)
        if source:
            params["source"] = source
        elif "source" in params:
            del params["source"]
        query = urlencode(params)
        return f"{base_url}?{query}" if query else base_url

    normalized = normalize_source_filter(active_source)
    return {
        "all": url_for(""),
        "polymarket": url_for(Market.Source.POLYMARKET),
        "kalshi": url_for(Market.Source.KALSHI),
        "active_source": normalized,
        "show_kalshi": kalshi_enabled(),
    }
