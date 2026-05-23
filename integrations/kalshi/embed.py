"""Build embedded Kalshi chart context for market detail pages."""

from django.conf import settings

from integrations.kalshi.chart import build_kalshi_chart_payload
from integrations.kalshi.urls import resolve_kalshi_market_url


def build_kalshi_embed_context(market):
    """Context dict for the Kalshi chart embed partial."""
    if market.source != market.Source.KALSHI:
        return None

    chart = build_kalshi_chart_payload(market)
    if not chart:
        return None

    return {
        "chart_data": chart,
        "embed_height": settings.KALSHI_EMBED_HEIGHT,
        "kalshi_url": resolve_kalshi_market_url(market),
        "yes_label": chart["yes_label"],
    }
