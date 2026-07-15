"""Compact bulky Polymarket API payloads on inactive markets.

Resolved/closed markets keep denormalized columns (title, outcomes, slugs,
browse areas, volume, card image). Full ``polymarket_raw`` / ``polymarket_event_raw``
blobs are only needed for live sync and are the main driver of DB size on Heroku.
"""

from __future__ import annotations

import json
from datetime import date

from django.db.models.functions import Coalesce
from django.utils import timezone

from integrations.polymarket.urls import get_parent_event_slug
from markets.models import Market

PRUNED_MARKER = "_pruned"

ORDER_FIFO = "fifo"
ORDER_PK = "pk"
VALID_PRUNE_ORDERS = frozenset({ORDER_FIFO, ORDER_PK})

DEFAULT_PRUNE_STATUSES = (
    Market.Status.RESOLVED,
    Market.Status.CLOSED,
)

# Retained in polymarket_raw: Polymarket URLs, forecast mode, match/orphan UI.
_RAW_KEEP_KEYS = (
    "slug",
    "groupItemTitle",
    "market_kind",
    "event_slug",
    "sportsMarketType",
    "team_a",
    "team_b",
    "team_a_icon",
    "team_b_icon",
    "question",
)


def parse_statuses(value: str) -> list[str]:
    """Parse comma-separated Market status values."""
    allowed = {choice.value for choice in Market.Status}
    statuses = []
    for part in (value or "").split(","):
        status = part.strip().lower()
        if not status:
            continue
        if status not in allowed:
            raise ValueError(
                f"Invalid status {status!r}. Choose from: {', '.join(sorted(allowed))}."
            )
        if status not in statuses:
            statuses.append(status)
    return statuses or list(DEFAULT_PRUNE_STATUSES)


def estimate_payload_bytes(market) -> int:
    """Approximate JSON payload size for one market row."""
    raw = market.polymarket_raw or {}
    event = market.polymarket_event_raw or {}
    return len(json.dumps(raw, separators=(",", ":"))) + len(
        json.dumps(event, separators=(",", ":"))
    )


def market_raw_is_already_pruned(market) -> bool:
    raw = market.polymarket_raw or {}
    event = market.polymarket_event_raw or {}
    return bool(raw.get(PRUNED_MARKER) or event.get(PRUNED_MARKER))


def compact_polymarket_raw_payloads(market) -> tuple[dict, dict]:
    """Build minimal (polymarket_raw, polymarket_event_raw) preserving URLs and UI hints."""
    raw = market.polymarket_raw or {}
    event_raw = market.polymarket_event_raw or {}
    today = date.today().isoformat()

    minimal_raw: dict = {PRUNED_MARKER: today}

    slug = market.polymarket_slug or raw.get("slug") or market.slug
    if slug:
        minimal_raw["slug"] = slug

    for key in _RAW_KEEP_KEYS:
        if key == "slug":
            continue
        value = raw.get(key)
        if value in (None, "", [], {}):
            continue
        minimal_raw[key] = value

    events = raw.get("events") or []
    if events and isinstance(events[0], dict):
        parent_slug = events[0].get("slug")
        if parent_slug:
            minimal_raw["events"] = [{"slug": parent_slug}]

    parent_slug = (
        event_raw.get("slug")
        or raw.get("event_slug")
        or get_parent_event_slug(market)
    )
    minimal_event: dict = {PRUNED_MARKER: today}
    if parent_slug:
        minimal_event["slug"] = str(parent_slug).strip()

    return minimal_raw, minimal_event


def market_raw_needs_pruning(market, *, min_saved_bytes: int = 512) -> bool:
    if market_raw_is_already_pruned(market):
        return False
    if market.source != Market.Source.POLYMARKET:
        return False
    before = estimate_payload_bytes(market)
    new_raw, new_event = compact_polymarket_raw_payloads(market)
    after = len(json.dumps(new_raw, separators=(",", ":"))) + len(
        json.dumps(new_event, separators=(",", ":"))
    )
    return before - after >= min_saved_bytes


def parse_order(value: str) -> str:
    order = (value or ORDER_FIFO).strip().lower()
    if order not in VALID_PRUNE_ORDERS:
        raise ValueError(
            f"Invalid order {order!r}. Choose from: {', '.join(sorted(VALID_PRUNE_ORDERS))}."
        )
    return order


def prune_market_raw_queryset(*, statuses=None, order: str = ORDER_FIFO):
    """Candidates for compaction, oldest inactive markets first by default (FIFO)."""
    statuses = statuses or list(DEFAULT_PRUNE_STATUSES)
    order = parse_order(order)
    queryset = Market.objects.filter(
        source=Market.Source.POLYMARKET,
        status__in=statuses,
    ).exclude(polymarket_raw__has_key=PRUNED_MARKER)

    if order == ORDER_FIFO:
        return queryset.annotate(
            _prune_sort_at=Coalesce(
                "resolution_date",
                "close_date",
                "updated_at",
                "created_at",
            )
        ).order_by("_prune_sort_at", "pk")

    return queryset.order_by("pk")


def empty_prune_stats() -> dict:
    return {
        "pending": 0,
        "examined": 0,
        "updated": 0,
        "skipped": 0,
        "bytes_before": 0,
        "bytes_after": 0,
    }


def run_market_raw_prune(
    *,
    statuses=None,
    limit: int = 0,
    batch_size: int = 500,
    dry_run: bool = False,
    min_saved_bytes: int = 512,
    order: str = ORDER_FIFO,
) -> dict:
    """Compact raw payloads for up to ``limit`` markets (0 = all candidates)."""
    statuses = statuses or list(DEFAULT_PRUNE_STATUSES)
    batch_size = max(1, batch_size)
    limit = max(0, limit)

    queryset = prune_market_raw_queryset(statuses=statuses, order=order)
    totals = empty_prune_stats()
    totals["pending"] = queryset.count()

    processed = 0

    while True:
        if limit and processed >= limit:
            break

        chunk_size = batch_size
        if limit:
            chunk_size = min(chunk_size, limit - processed)

        # Always take from the start: compacted rows drop out of the queryset
        # via the pruned-marker exclude, so an advancing offset would skip work.
        batch = list(queryset[:chunk_size])
        if not batch:
            break

        merge_prune_stats(
            totals,
            prune_market_raw_batch(
                batch,
                dry_run=dry_run,
                min_saved_bytes=min_saved_bytes,
            ),
        )
        processed += len(batch)
        if dry_run:
            # Dry-run does not mark rows pruned; advance past this slice.
            queryset = queryset.exclude(pk__in=[m.pk for m in batch])

    return totals


def prune_market_raw_batch(
    markets,
    *,
    dry_run: bool = False,
    min_saved_bytes: int = 512,
) -> dict:
    """Compact raw payloads for an iterable of markets. Returns summary stats."""
    stats = {
        "examined": 0,
        "updated": 0,
        "skipped": 0,
        "bytes_before": 0,
        "bytes_after": 0,
    }
    to_update: list[Market] = []
    now = timezone.now()

    for market in markets:
        stats["examined"] += 1
        if not market_raw_needs_pruning(market, min_saved_bytes=min_saved_bytes):
            stats["skipped"] += 1
            continue

        before = estimate_payload_bytes(market)
        new_raw, new_event = compact_polymarket_raw_payloads(market)
        after = len(json.dumps(new_raw, separators=(",", ":"))) + len(
            json.dumps(new_event, separators=(",", ":"))
        )
        stats["bytes_before"] += before
        stats["bytes_after"] += after
        stats["updated"] += 1

        if dry_run:
            continue

        market.polymarket_raw = new_raw
        market.polymarket_event_raw = new_event
        market.updated_at = now
        to_update.append(market)

    if to_update and not dry_run:
        Market.objects.bulk_update(
            to_update,
            ["polymarket_raw", "polymarket_event_raw", "updated_at"],
            batch_size=500,
        )

    return stats


def merge_prune_stats(total: dict, batch: dict) -> dict:
    for key in total:
        total[key] += batch.get(key, 0)
    return total


def format_bytes(num_bytes: int) -> str:
    if num_bytes >= 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    if num_bytes >= 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes} B"
