"""Unified market sync orchestration across external sources."""

import logging
from dataclasses import dataclass, field

from django.conf import settings
from django.db import OperationalError, close_old_connections
from django.db.models import Q
from django.utils import timezone

from integrations.market_refresh import (
    attach_refresh_routing_raw,
    is_postgres_out_of_memory,
    load_market_for_refresh,
)
from integrations.services import (
    _log_polymarket_fetch_failure,
    refresh_market_from_polymarket,
    sync_binary_markets_by_tag,
    sync_top_volume_polymarket_markets,
)
from markets.categories import CANONICAL_CATEGORIES, CanonicalCategory, FIFA_WORLD_CUP_CATEGORY_SLUG
from markets.models import Market

logger = logging.getLogger(__name__)

_TRANSIENT_DB_ERROR_MARKERS = ("ssl", "eof", "connection reset", "closed unexpectedly")


def _materialize_queryset(queryset):
    """Evaluate a queryset, retrying once after stale PostgreSQL SSL drops."""
    try:
        return list(queryset)
    except OperationalError as exc:
        message = str(exc).lower()
        if not any(marker in message for marker in _TRANSIENT_DB_ERROR_MARKERS):
            raise
        close_old_connections()
        return list(queryset)


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
        except Exception as exc:
            _log_polymarket_fetch_failure(
                exc, "World Cup match sync failed for category %s", category.slug
            )
        if summary.imported or summary.updated:
            from markets.selectors import invalidate_category_summaries_cache

            invalidate_category_summaries_cache()
        return summary

    if category.slug == "sports":
        try:
            from integrations.services import sync_f1_markets, sync_h2h_match_markets

            summary.absorb(sync_h2h_match_markets())
            summary.absorb(sync_f1_markets())
        except Exception as exc:
            _log_polymarket_fetch_failure(
                exc, "H2H/F1 sports sync failed for category %s", category.slug
            )

    if category.slug == "esports":
        try:
            from integrations.polymarket.head_to_head_matches import ESPORTS_H2H_MATCH_TAG_SLUGS
            from integrations.services import sync_h2h_match_markets

            summary.absorb(
                sync_h2h_match_markets(
                    tag_slugs=ESPORTS_H2H_MATCH_TAG_SLUGS,
                    default_category=category.name,
                )
            )
        except Exception as exc:
            _log_polymarket_fetch_failure(
                exc, "Esports H2H sync failed for category %s", category.slug
            )

    if category.polymarket_tag:
        try:
            summary.absorb(
                sync_binary_markets_by_tag(
                    tag_slug=category.polymarket_tag,
                    default_category=category.name,
                    limit=limit,
                )
            )
        except Exception as exc:
            _log_polymarket_fetch_failure(
                exc, "Polymarket category sync failed for %s", category.slug
            )

    if summary.imported or summary.updated:
        from markets.selectors import invalidate_category_summaries_cache

        invalidate_category_summaries_cache()

    return summary


def sync_all_category_markets(*, limit=None) -> dict:
    """Sync every canonical category from Polymarket."""
    limit = limit or settings.MARKET_SYNC_CATEGORY_LIMIT
    totals = SyncSummary()
    per_category = {}

    try:
        totals.absorb(sync_top_volume_polymarket_markets())
    except Exception as exc:
        _log_polymarket_fetch_failure(exc, "Polymarket top-volume sync failed")

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

    from markets.selectors import invalidate_category_summaries_cache

    invalidate_category_summaries_cache()

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

    due_market_ids = (
        Market.objects.filter(source=Market.Source.POLYMARKET)
        .filter(
            Q(status=Market.Status.OPEN)
            | Q(status=Market.Status.CLOSED, resolved_outcome="")
            | Q(status=Market.Status.RESOLVED, resolved_outcome="")
        )
        .filter(
            Q(polymarket_synced_at__isnull=True)
            | Q(polymarket_synced_at__lte=cutoff)
            | Q(close_date__lte=now)
            | Q(game_start_time__lte=now)
            | Q(accepting_orders=False)
            | Q(status=Market.Status.CLOSED, resolved_outcome="")
            | Q(status=Market.Status.RESOLVED, resolved_outcome="")
        )
        .order_by("polymarket_synced_at", "updated_at")
        .values_list("pk", flat=True)[:batch_size]
    )

    try:
        candidate_ids = _materialize_queryset(due_market_ids)
    except OperationalError as exc:
        if is_postgres_out_of_memory(exc):
            logger.warning(
                "Stale market refresh skipped — PostgreSQL out of memory on candidate fetch"
            )
            candidate_ids = []
        else:
            raise

    for market_id in candidate_ids:
        try:
            market = load_market_for_refresh(market_id)
        except OperationalError as exc:
            if is_postgres_out_of_memory(exc):
                logger.warning(
                    "Stale market refresh skipped market %s — PostgreSQL out of memory on load",
                    market_id,
                )
                failures += 1
                continue
            raise
        if market is None:
            continue

        attach_refresh_routing_raw(market)
        try:
            refresh_market(market)
            refreshed += 1
        except OperationalError as exc:
            if is_postgres_out_of_memory(exc):
                logger.warning(
                    "Stale market refresh skipped market %s — PostgreSQL out of memory during refresh",
                    market_id,
                )
                failures += 1
                continue
            failures += 1
            logger.exception("Failed to refresh stale market %s", market.external_id)
        except Exception:
            failures += 1
            logger.exception("Failed to refresh stale market %s", market.external_id)

    logger.info(
        "Stale market refresh complete: %s refreshed, %s failed (batch=%s)",
        refreshed,
        failures,
        batch_size,
    )

    from integrations.services import repair_resolved_markets_with_pending_predictions

    repair = repair_resolved_markets_with_pending_predictions(limit=batch_size)
    if (
        repair["resolved_predictions"]
        or repair["repaired_markets"]
        or repair.get("rescored_predictions")
    ):
        logger.info(
            "Resolved-market repair: %s markets backfilled, %s predictions scored, "
            "%s multi-binary forecasts rescored",
            repair["repaired_markets"],
            repair["resolved_predictions"],
            repair.get("rescored_predictions", 0),
        )

    return {
        "refreshed": refreshed,
        "failures": failures,
        "candidates": len(candidate_ids),
        "repair": repair,
    }
