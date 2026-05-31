"""Unified market sync orchestration across external sources."""

import logging
from dataclasses import dataclass, field

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from integrations.services import (
    refresh_market_from_polymarket,
    sync_binary_markets_by_tag,
    sync_top_volume_polymarket_markets,
)
from markets.categories import CANONICAL_CATEGORIES, CanonicalCategory, FIFA_WORLD_CUP_CATEGORY_SLUG
from markets.models import Market

logger = logging.getLogger(__name__)


@dataclass
class SyncSummary:
    imported: int = 0
    updated: int = 0
    errors: list[dict] = field(default_factory=list)

    def absorb(self, result: dict | None) -> None:
        if not result:
            return
        for item in result.get("imported", []):
            if item.get("created"):
                self.imported += 1
            else:
                self.updated += 1
        self.errors.extend(result.get("errors", []))


def refresh_market(market):
    """Refresh a market from its configured external source."""
    if market.source == Market.Source.POLYMARKET:
        return refresh_market_from_polymarket(market)
    return market


def sync_category_markets(category: CanonicalCategory, *, limit=None) -> SyncSummary:
    """Import fresh markets for a browse category from Polymarket."""
    limit = limit or settings.MARKET_SYNC_CATEGORY_LIMIT
    summary = SyncSummary()

    if category.slug == FIFA_WORLD_CUP_CATEGORY_SLUG:
        try:
            from integrations.services import sync_world_cup_match_markets

            summary.absorb(sync_world_cup_match_markets())
        except Exception:
            logger.exception("World Cup match sync failed for category %s", category.slug)
        return summary

    if category.polymarket_tag:
        try:
            summary.absorb(
                sync_binary_markets_by_tag(
                    tag_slug=category.polymarket_tag,
                    default_category=category.name,
                    limit=limit,
                )
            )
        except Exception:
            logger.exception("Polymarket category sync failed for %s", category.slug)

    return summary


def sync_all_category_markets(*, limit=None) -> dict:
    """Sync every canonical category from Polymarket."""
    limit = limit or settings.MARKET_SYNC_CATEGORY_LIMIT
    totals = SyncSummary()
    per_category = {}

    try:
        totals.absorb(sync_top_volume_polymarket_markets())
    except Exception:
        logger.exception("Polymarket top-volume sync failed")

    for category in CANONICAL_CATEGORIES:
        if not category.polymarket_tag:
            continue
        summary = sync_category_markets(category, limit=limit)
        per_category[category.slug] = {
            "imported": summary.imported,
            "updated": summary.updated,
            "errors": len(summary.errors),
        }
        totals.imported += summary.imported
        totals.updated += summary.updated
        totals.errors.extend(summary.errors)

    logger.info(
        "Category sync complete: %s imported, %s updated, %s errors",
        totals.imported,
        totals.updated,
        len(totals.errors),
    )
    return {
        "imported": totals.imported,
        "updated": totals.updated,
        "errors": totals.errors,
        "categories": per_category,
    }


def refresh_stale_open_markets(*, batch_size=None, stale_minutes=None) -> dict:
    """Refresh open imported markets whose source state may have changed.

    Besides normal staleness, locally elapsed close/kickoff times are refreshed
    immediately so resolution status does not wait for the full catalog sync.
    """
    batch_size = batch_size or settings.MARKET_SYNC_STALE_BATCH_SIZE
    stale_minutes = stale_minutes or settings.MARKET_SYNC_STALE_MINUTES
    now = timezone.now()
    cutoff = now - timezone.timedelta(minutes=stale_minutes)

    refreshed = 0
    failures = 0

    due_markets = (
        Market.objects.filter(
            status=Market.Status.OPEN,
            source=Market.Source.POLYMARKET,
        )
        .filter(
            Q(polymarket_synced_at__isnull=True)
            | Q(polymarket_synced_at__lte=cutoff)
            | Q(close_date__lte=now)
            | Q(game_start_time__lte=now)
            | Q(accepting_orders=False)
        )
        .order_by("polymarket_synced_at", "updated_at")[:batch_size]
    )

    candidates = list(due_markets)

    for market in candidates:
        try:
            refresh_market(market)
            refreshed += 1
        except Exception:
            failures += 1
            logger.exception("Failed to refresh stale market %s", market.external_id)

    logger.info(
        "Stale market refresh complete: %s refreshed, %s failed (batch=%s)",
        refreshed,
        failures,
        batch_size,
    )
    return {"refreshed": refreshed, "failures": failures, "candidates": len(candidates)}
