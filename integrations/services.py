"""Market import service — decoupled from Polymarket client."""

import logging

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.text import slugify

from integrations.polymarket.constants import MULTI_OUTCOME_EVENT_KIND, POLYMARKET_EVENT_EXTERNAL_PREFIX
from integrations.polymarket.client import (
    PolymarketClient,
    build_polymarket_event_raw,
    normalize_polymarket_event_record,
    normalize_polymarket_record,
)
from markets.models import Market
from predictions.services import resolve_market_predictions

logger = logging.getLogger(__name__)


def _fetch_event_for_market(client, raw_market, raw_event=None):
    """Resolve parent event payload for a Polymarket market record."""
    if raw_event:
        return raw_event

    raw_event = None
    events = raw_market.get("events") or []
    event_slug = None

    if events and isinstance(events[0], dict):
        raw_event = events[0]
        event_slug = events[0].get("slug")
    else:
        event_slug = raw_market.get("slug")

    if event_slug and not raw_event:
        try:
            fetched = client.fetch_event_by_slug(event_slug)
            if fetched and fetched.get("slug"):
                raw_event = fetched
        except Exception:
            logger.exception("Failed to fetch Polymarket event %s", event_slug)
    elif event_slug and raw_event and not raw_event.get("markets"):
        try:
            fetched = client.fetch_event_by_slug(event_slug)
            if fetched and fetched.get("markets"):
                raw_event = fetched
        except Exception:
            logger.exception("Failed to fetch Polymarket event %s", event_slug)

    return raw_event or {}


def backfill_market_resolved_outcome(market, *, raw_market=None):
    """Fill missing ``resolved_outcome`` from stored or fresh Polymarket raw payloads."""
    if market.resolved_outcome or market.status != Market.Status.RESOLVED:
        return market

    from integrations.polymarket.client import infer_binary_resolved_outcome, normalize_polymarket_event_record

    raw = raw_market or market.polymarket_raw or {}
    inferred = ""

    if (
        raw.get("market_kind") == MULTI_OUTCOME_EVENT_KIND
        and market.polymarket_event_raw
    ):
        normalized = normalize_polymarket_event_record(
            market.polymarket_event_raw,
            default_category=market.category or "",
            require_open=False,
        )
        if normalized:
            inferred = normalized.get("resolved_outcome") or ""

    if not inferred:
        inferred = infer_binary_resolved_outcome(raw)
    if not inferred:
        return market

    market.resolved_outcome = inferred
    market.save(update_fields=["resolved_outcome", "updated_at"])
    return market


def repair_resolved_markets_with_pending_predictions(*, limit=200):
    """Refresh Polymarket state, backfill outcomes, and score stuck pending forecasts."""
    from predictions.models import Prediction

    candidates = (
        Market.objects.filter(source=Market.Source.POLYMARKET)
        .filter(predictions__status=Prediction.Status.PENDING)
        .distinct()
        .order_by("-updated_at")[:limit]
    )
    repaired_markets = 0
    resolved_predictions = 0
    refreshed_markets = 0

    for market in candidates:
        before_outcome = market.resolved_outcome
        before_status = market.status

        if not market.resolved_outcome or market.status != Market.Status.RESOLVED:
            try:
                market = refresh_market_from_polymarket(market)
                market.refresh_from_db()
                if market.status != before_status or market.resolved_outcome != before_outcome:
                    refreshed_markets += 1
            except Exception:
                logger.exception(
                    "Failed to refresh Polymarket market %s during repair",
                    market.external_id,
                )

        market = backfill_market_resolved_outcome(market)
        if market.resolved_outcome and not before_outcome:
            repaired_markets += 1
        if market.status == Market.Status.RESOLVED and market.resolved_outcome:
            resolved_predictions += len(resolve_market_predictions(market))

    return {
        "repaired_markets": repaired_markets,
        "resolved_predictions": resolved_predictions,
        "refreshed_markets": refreshed_markets,
        "candidates": len(candidates),
    }


def import_market_from_normalized(data, *, raw_market=None, raw_event=None):
    """Create or update a Market from normalized import data."""
    external_id = data["external_id"]
    source = data.get("source", Market.Source.POLYMARKET)

    defaults = {
        "title": data["title"],
        "description": data.get("description", ""),
        "category": data.get("category", ""),
        "source": source,
        "status": data.get("status", Market.Status.OPEN),
        "outcomes": data.get("outcomes", []),
        "current_probability": data.get("current_probability", {}),
        "close_date": data.get("close_date"),
        "resolution_date": data.get("resolution_date"),
        "resolved_outcome": data.get("resolved_outcome", ""),
        "accepting_orders": data.get("accepting_orders", True),
        "game_start_time": data.get("game_start_time"),
    }

    if source == Market.Source.POLYMARKET:
        defaults["polymarket_slug"] = data.get("polymarket_slug") or ""
        defaults["polymarket_synced_at"] = timezone.now()
        if raw_market is not None:
            defaults["polymarket_raw"] = raw_market
        if raw_event is not None:
            defaults["polymarket_event_raw"] = raw_event

    existing_market = Market.objects.filter(external_id=external_id).first()
    from markets.translation_services import apply_spanish_translations_to_defaults

    apply_spanish_translations_to_defaults(defaults, existing_market=existing_market)

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

        if market.status == Market.Status.RESOLVED:
            market = backfill_market_resolved_outcome(market, raw_market=raw_market)
            if market.resolved_outcome:
                resolve_market_predictions(market)

        from markets.display_metadata import sync_market_display_metadata

        sync_market_display_metadata(market, save=True)

    return market, created


def refresh_market_from_polymarket(market):
    """Fetch latest Polymarket market + event data and update local record."""
    if market.source != Market.Source.POLYMARKET or not market.external_id:
        return market

    from integrations.polymarket.soccer_matches import is_world_cup_match_market

    if is_world_cup_match_market(market):
        return refresh_world_cup_match_market(market)

    if (
        market.external_id.startswith(POLYMARKET_EVENT_EXTERNAL_PREFIX)
        or (market.polymarket_raw or {}).get("market_kind") == MULTI_OUTCOME_EVENT_KIND
    ):
        return refresh_polymarket_multi_outcome_market(market)

    client = PolymarketClient()
    try:
        raw_market = client.fetch_market_by_id(market.external_id)
    except Exception:
        logger.exception("Failed to fetch Polymarket market %s", market.external_id)
        return market

    raw_event = _fetch_event_for_market(client, raw_market)
    if raw_event and not raw_market.get("volumeNum") and not raw_market.get("volume"):
        market_id = str(raw_market.get("id") or market.external_id)
        for candidate in raw_event.get("markets") or []:
            if str(candidate.get("id")) == market_id:
                raw_market = candidate
                break

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


def refresh_polymarket_multi_outcome_market(market):
    """Refresh a composite Polymarket event represented as a multi-outcome market."""
    client = PolymarketClient()
    slug = market.polymarket_slug or (market.polymarket_raw or {}).get("event_slug")
    if not slug and market.external_id.startswith(POLYMARKET_EVENT_EXTERNAL_PREFIX):
        slug = market.external_id.removeprefix(POLYMARKET_EVENT_EXTERNAL_PREFIX)
    if not slug:
        return market

    try:
        event = client.fetch_event_by_slug(slug)
    except Exception:
        logger.exception("Failed to fetch Polymarket event %s", slug)
        return market
    if not event:
        return market

    normalized = normalize_polymarket_event_record(
        event,
        default_category=market.category or "",
        require_open=False,
    )
    if not normalized:
        return market

    raw_market = build_polymarket_event_raw(event, normalized=normalized)
    market, _ = import_market_from_normalized(
        normalized,
        raw_market=raw_market,
        raw_event=event,
    )
    return market


def import_markets_from_polymarket(*, limit=50, offset=0, active=True):
    client = PolymarketClient()
    raw_markets = client.fetch_markets(
        limit=limit,
        offset=offset,
        active=active,
        closed=False if active else None,
        order="volumeNum",
    )

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


def _import_polymarket_market_pairs(client, pairs, *, default_category=""):
    imported = []
    errors = []
    event_cache = {}

    for raw_market, raw_event in pairs:
        try:
            if not raw_market.get("id"):
                continue

            event_slug = (raw_event or {}).get("slug")
            if event_slug:
                if event_slug not in event_cache:
                    needs_full_event = not raw_market.get("volumeNum") and not raw_market.get("volume")
                    if needs_full_event:
                        try:
                            fetched = client.fetch_event_by_slug(event_slug)
                            event_cache[event_slug] = fetched if fetched else (raw_event or {})
                        except Exception:
                            logger.exception("Failed to fetch Polymarket event %s", event_slug)
                            event_cache[event_slug] = raw_event or {}
                    else:
                        event_cache[event_slug] = raw_event or {}

                cached_event = event_cache[event_slug]
                market_id = str(raw_market.get("id"))
                for candidate in cached_event.get("markets") or []:
                    if str(candidate.get("id")) == market_id:
                        raw_market = candidate
                        raw_event = cached_event
                        break

            if raw_market.get("market_kind") == MULTI_OUTCOME_EVENT_KIND:
                normalized = normalize_polymarket_event_record(
                    raw_event or {},
                    default_category=default_category or raw_market.get("category") or "",
                )
                if not normalized:
                    continue
            else:
                normalized = normalize_polymarket_record(
                    raw_market,
                    default_category=default_category or raw_market.get("category") or "",
                )
            market, created = import_market_from_normalized(
                normalized,
                raw_market=raw_market,
                raw_event=raw_event or _fetch_event_for_market(client, raw_market),
            )
            imported.append({"market": market, "created": created, "raw": raw_market})
        except Exception as exc:
            logger.exception("Failed to import Polymarket market: %s", raw_market.get("id"))
            errors.append({"raw_id": raw_market.get("id"), "error": str(exc)})

    return {"imported": imported, "errors": errors}


def sync_top_volume_polymarket_markets(*, min_volume_share=None, max_markets=None):
    """Import high-volume Polymarket markets aligned with Polymarket browse rankings."""
    from django.conf import settings

    client = PolymarketClient()
    pairs = client.fetch_top_volume_market_pairs(
        min_volume_share=min_volume_share
        if min_volume_share is not None
        else getattr(settings, "POLYMARKET_TOP_VOLUME_MIN_SHARE", 0.5),
        max_markets=max_markets
        if max_markets is not None
        else getattr(settings, "POLYMARKET_TOP_VOLUME_MAX_MARKETS", 500),
        max_event_pages=getattr(settings, "POLYMARKET_TOP_VOLUME_MAX_EVENT_PAGES", 15),
    )
    return _import_polymarket_market_pairs(client, pairs)


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


def sync_binary_markets_by_tag(*, tag_slug, default_category, limit=48):
    """Fetch importable markets for a Polymarket tag and upsert locally."""
    from django.conf import settings

    client = PolymarketClient()
    pairs = client.fetch_market_pairs_by_tag(
        tag_slug,
        limit=limit,
        default_category=default_category,
        max_event_pages=getattr(settings, "POLYMARKET_TAG_SYNC_MAX_EVENT_PAGES", 10),
    )
    return _import_polymarket_market_pairs(
        client,
        pairs,
        default_category=default_category,
    )


def sync_economy_binary_markets(*, limit=12):
    """Fetch Economy Yes/No markets from Polymarket and upsert locally."""
    return sync_binary_markets_by_tag(
        tag_slug="economy",
        default_category="Economy",
        limit=limit,
    )


def sync_crypto_binary_markets(*, limit=48):
    """Fetch Crypto Yes/No markets from Polymarket and upsert locally."""
    return sync_binary_markets_by_tag(
        tag_slug="crypto",
        default_category="Crypto",
        limit=limit,
    )


def _world_cup_sync_limit(limit):
    """Resolve sync cap; 0 or None means import all available group-stage matches."""
    from django.conf import settings

    if limit is None:
        limit = getattr(settings, "WORLD_CUP_MATCH_SYNC_LIMIT", 0)
    if not limit:
        return None
    return limit


def sync_world_cup_match_markets(*, limit=None):
    """Fetch FIFA World Cup match events and upsert as 3-outcome markets."""
    from integrations.polymarket.soccer_matches import (
        build_world_cup_match_raw,
        normalize_world_cup_match_event,
    )

    client = PolymarketClient()
    events = client.fetch_world_cup_match_events(limit=_world_cup_sync_limit(limit))

    imported = []
    errors = []

    for event in events:
        try:
            normalized = normalize_world_cup_match_event(event, default_category="Sports")
            if not normalized:
                continue
            raw_market = build_world_cup_match_raw(event, normalized=normalized)
            market, created = import_market_from_normalized(
                normalized,
                raw_market=raw_market,
                raw_event=event,
            )
            imported.append({"market": market, "created": created, "raw": event})
        except Exception as exc:
            logger.exception("Failed to import World Cup match event: %s", event.get("slug"))
            errors.append({"raw_id": event.get("slug"), "error": str(exc)})

    return {"imported": imported, "errors": errors}


def refresh_world_cup_match_market(market):
    """Refresh a composite World Cup match market from its Polymarket event."""
    from integrations.polymarket.soccer_matches import (
        WORLD_CUP_MATCH_EXTERNAL_PREFIX,
        build_world_cup_match_raw,
        is_world_cup_match_market,
        normalize_world_cup_match_event,
    )

    if not is_world_cup_match_market(market):
        return market

    client = PolymarketClient()
    slug = market.polymarket_slug
    if not slug and market.external_id.startswith(WORLD_CUP_MATCH_EXTERNAL_PREFIX):
        slug = market.external_id.removeprefix(WORLD_CUP_MATCH_EXTERNAL_PREFIX)
    if not slug:
        return market

    try:
        event = client.fetch_event_by_slug(slug)
    except Exception:
        logger.exception("Failed to fetch World Cup match event %s", slug)
        return market

    if not event:
        return market

    normalized = normalize_world_cup_match_event(
        event,
        default_category=market.category or "Sports",
    )
    if not normalized:
        return market

    raw_market = build_world_cup_match_raw(event, normalized=normalized)
    market, _ = import_market_from_normalized(
        normalized,
        raw_market=raw_market,
        raw_event=event,
    )
    return market


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
