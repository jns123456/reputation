"""Helpers for background Polymarket refresh without loading bulky JSON blobs."""

from __future__ import annotations

import logging

from django.db import OperationalError
from django.db.models.fields.json import KeyTextTransform

from markets.models import Market

logger = logging.getLogger(__name__)

REFRESH_MARKET_DEFER_FIELDS = (
    "description",
    "description_es",
    "polymarket_raw",
    "polymarket_event_raw",
)

_POSTGRES_OOM_MARKERS = ("out of memory", "could not allocate memory")


def is_postgres_out_of_memory(exc: BaseException) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _POSTGRES_OOM_MARKERS)


def load_market_for_refresh(market_id: int):
    """Load a market for Celery refresh while skipping large Polymarket payloads."""
    return (
        Market.objects.defer(*REFRESH_MARKET_DEFER_FIELDS)
        .filter(pk=market_id)
        .first()
    )


def market_raw_json_hints(market_id: int) -> dict[str, str]:
    """Extract small routing keys from polymarket_raw without loading the full blob."""
    row = (
        Market.objects.filter(pk=market_id)
        .annotate(
            market_kind=KeyTextTransform("market_kind", "polymarket_raw"),
            event_slug=KeyTextTransform("event_slug", "polymarket_raw"),
            group_item_title=KeyTextTransform("groupItemTitle", "polymarket_raw"),
            sports_market_type=KeyTextTransform("sportsMarketType", "polymarket_raw"),
        )
        .values(
            "market_kind",
            "event_slug",
            "group_item_title",
            "sports_market_type",
        )
        .first()
    )
    if not row:
        return {}

    hints = {}
    if row.get("market_kind"):
        hints["market_kind"] = row["market_kind"]
    if row.get("event_slug"):
        hints["event_slug"] = row["event_slug"]
    if row.get("group_item_title"):
        hints["groupItemTitle"] = row["group_item_title"]
    if row.get("sports_market_type"):
        hints["sportsMarketType"] = row["sports_market_type"]
    return hints


def attach_refresh_routing_raw(market) -> None:
    """Populate in-memory polymarket_raw hints so routing avoids a deferred-field fetch."""
    if market is None:
        return

    deferred = market.get_deferred_fields()
    if "polymarket_raw" not in deferred:
        return

    hints = market_raw_json_hints(market.pk)
    if hints:
        market.polymarket_raw = hints
