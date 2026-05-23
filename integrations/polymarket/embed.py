"""Build URLs for Polymarket's official embed widget (https://embed.polymarket.com/)."""

from urllib.parse import urlencode

from django.conf import settings

from integrations.polymarket.urls import (
    get_polymarket_embed_slug,
    resolve_polymarket_market_url,
    resolve_polymarket_public_url,
)


def build_polymarket_embed_url(market_slug, **overrides):
    """
    Build iframe src for Polymarket market embed.

    See: https://embed.polymarket.com/ and Polymarket Help Center embed docs.
    """
    params = {
        "market": market_slug,
        "theme": settings.POLYMARKET_EMBED_THEME,
        "features": settings.POLYMARKET_EMBED_FEATURES,
        "layout": settings.POLYMARKET_EMBED_LAYOUT,
        "width": settings.POLYMARKET_EMBED_CONTENT_WIDTH,
    }
    if settings.POLYMARKET_EMBED_BORDER:
        params["border"] = "true"
    params.update({k: v for k, v in overrides.items() if v is not None})
    params = {k: v for k, v in params.items() if v not in ("", None, False)}

    base = settings.POLYMARKET_EMBED_BASE_URL.rstrip("/")
    return f"{base}?{urlencode(params)}"


def build_polymarket_embed_context(market):
    """Context dict for the embed partial template."""
    slug = get_polymarket_embed_slug(market)
    if not slug or market.source != market.Source.POLYMARKET:
        return None

    return {
        "embed_url": build_polymarket_embed_url(slug),
        "embed_slug": slug,
        "embed_width": settings.POLYMARKET_EMBED_WIDTH,
        "embed_height": settings.POLYMARKET_EMBED_HEIGHT,
        "polymarket_url": resolve_polymarket_public_url(market),
        "polymarket_market_url": resolve_polymarket_market_url(market),
        "embed_generator_url": "https://embed.polymarket.com/",
    }
