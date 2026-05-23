"""Market import service — decoupled from Polymarket client."""

import logging

from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from integrations.polymarket.client import PolymarketClient, normalize_polymarket_record
from markets.models import Market
from predictions.services import resolve_market_predictions

logger = logging.getLogger(__name__)


def _fetch_event_for_market(client, raw_market):
    """Resolve parent event payload for a Polymarket market record."""
    raw_event = None
    events = raw_market.get("events") or []
    event_slug = None

    if events and isinstance(events[0], dict):
        raw_event = events[0]
        event_slug = events[0].get("slug")
    else:
        event_slug = raw_market.get("slug")

    if event_slug and (not raw_event or not raw_event.get("markets")):
        try:
            fetched = client.fetch_event_by_slug(event_slug)
            if fetched and fetched.get("slug"):
                raw_event = fetched
        except Exception:
            logger.exception("Failed to fetch Polymarket event %s", event_slug)

    return raw_event


def import_market_from_normalized(data, *, raw_market=None, raw_event=None):
    """Create or update a Market from normalized import data."""
    external_id = data["external_id"]
    polymarket_slug = data.get("polymarket_slug") or ""

    defaults = {
        "title": data["title"],
        "description": data.get("description", ""),
        "category": data.get("category", ""),
        "source": data.get("source", Market.Source.POLYMARKET),
        "status": data.get("status", Market.Status.OPEN),
        "outcomes": data.get("outcomes", []),
        "current_probability": data.get("current_probability", {}),
        "close_date": data.get("close_date"),
        "resolution_date": data.get("resolution_date"),
        "resolved_outcome": data.get("resolved_outcome", ""),
        "polymarket_slug": polymarket_slug,
        "polymarket_synced_at": timezone.now(),
    }
    if raw_market is not None:
        defaults["polymarket_raw"] = raw_market
    if raw_event is not None:
        defaults["polymarket_event_raw"] = raw_event

    with transaction.atomic():
        market, created = Market.objects.update_or_create(
            external_id=external_id,
            defaults=defaults,
        )

        if not market.slug:
            base = slugify(market.title)[:500] or "market"
            slug = base
            counter = 1
            while Market.objects.filter(slug=slug).exclude(pk=market.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            market.slug = slug
            market.save(update_fields=["slug", "updated_at"])

        if market.status == Market.Status.RESOLVED and market.resolved_outcome:
            resolve_market_predictions(market)

    return market, created


def refresh_market_from_polymarket(market):
    """Fetch latest Polymarket market + event data and update local record."""
    if market.source != Market.Source.POLYMARKET or not market.external_id:
        return market

    client = PolymarketClient()
    try:
        raw_market = client.fetch_market_by_id(market.external_id)
    except Exception:
        logger.exception("Failed to fetch Polymarket market %s", market.external_id)
        return market

    raw_event = _fetch_event_for_market(client, raw_market)

    normalized = normalize_polymarket_record(
        raw_market,
        default_category=market.category or "",
    )
    market, _ = import_market_from_normalized(
        normalized,
        raw_market=raw_market,
        raw_event=raw_event or {},
    )
    return market


def import_markets_from_polymarket(*, limit=50, offset=0, active=True):
    client = PolymarketClient()
    raw_markets = client.fetch_markets(limit=limit, offset=offset, active=active)

    imported = []
    errors = []

    for raw in raw_markets:
        try:
            normalized = normalize_polymarket_record(raw)
            raw_event = _fetch_event_for_market(client, raw)
            market, created = import_market_from_normalized(
                normalized,
                raw_market=raw,
                raw_event=raw_event,
            )
            imported.append({"market": market, "created": created})
        except Exception as exc:
            logger.exception("Failed to import market: %s", raw.get("id"))
            errors.append({"raw_id": raw.get("id"), "error": str(exc)})

    return {"imported": imported, "errors": errors}


def sync_market_by_external_id(external_id):
    client = PolymarketClient()
    raw = client.fetch_market_by_id(external_id)
    normalized = normalize_polymarket_record(raw)
    raw_event = _fetch_event_for_market(client, raw)
    return import_market_from_normalized(
        normalized,
        raw_market=raw,
        raw_event=raw_event,
    )


def sync_economy_binary_markets(*, limit=12):
    """Fetch Economy Yes/No markets from Polymarket and upsert locally."""
    client = PolymarketClient()
    raw_markets = client.fetch_economy_binary_markets(limit=limit)

    imported = []
    errors = []

    for raw in raw_markets:
        try:
            if not raw.get("id"):
                continue
            normalized = normalize_polymarket_record(raw, default_category="Economy")
            raw_event = _fetch_event_for_market(client, raw)
            market, created = import_market_from_normalized(
                normalized,
                raw_market=raw,
                raw_event=raw_event,
            )
            imported.append({"market": market, "created": created, "raw": raw})
        except Exception as exc:
            logger.exception("Failed to import economy market: %s", raw.get("id"))
            errors.append({"raw_id": raw.get("id"), "error": str(exc)})

    return {"imported": imported, "errors": errors}


def get_economy_binary_markets(*, limit=12, sync=True):
    """Return Economy binary markets, optionally syncing from Polymarket first."""
    if sync:
        sync_economy_binary_markets(limit=limit)

    return (
        Market.objects.filter(
            category__iexact="Economy",
            status=Market.Status.OPEN,
            source=Market.Source.POLYMARKET,
        )
        .order_by("-updated_at")[:limit]
    )
