"""Unified market sync orchestration across external sources."""

import logging
from dataclasses import dataclass, field

import requests
from django.conf import settings
from django.utils import timezone

from integrations.kalshi.client import KalshiRateLimitError
from integrations.services import (
    refresh_market_from_kalshi,
    refresh_market_from_polymarket,
    sync_binary_markets_by_tag,
    sync_kalshi_markets_by_series,
    sync_top_volume_polymarket_markets,
)
from markets.categories import CANONICAL_CATEGORIES, CanonicalCategory, FIFA_WORLD_CUP_CATEGORY_SLUG
from markets.models import Market
from markets.source_filters import kalshi_enabled

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
    if market.source == Market.Source.KALSHI and kalshi_enabled():
        return refresh_market_from_kalshi(market)
    return market


def sync_category_markets(category: CanonicalCategory, *, limit=None, kalshi_lightweight=True) -> SyncSummary:
    """Import fresh markets for a browse category from all configured sources."""
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

    if not kalshi_enabled() or not category.kalshi_series_tickers:
        return summary

    kalshi_limit = (
        getattr(settings, "KALSHI_SYNC_CATEGORY_LIMIT", 12)
        if kalshi_lightweight
        else limit
    )
    series_tickers = list(category.kalshi_series_tickers)
    if kalshi_lightweight:
        series_tickers = series_tickers[: getattr(settings, "KALSHI_SYNC_CATEGORY_SERIES_LIMIT", 2)]

    for series_ticker in series_tickers:
        try:
            summary.absorb(
                sync_kalshi_markets_by_series(
                    series_ticker=series_ticker,
                    default_category=category.name,
                    limit=kalshi_limit,
                    fetch_events=not kalshi_lightweight,
                    include_metadata=True,
                )
            )
        except KalshiRateLimitError:
            logger.warning(
                "Kalshi rate limit hit syncing %s for category %s — stopping Kalshi sync",
                series_ticker,
                category.slug,
            )
            summary.errors.append({"raw_id": series_ticker, "error": "rate_limited"})
            break
        except requests.HTTPError as exc:
            logger.exception(
                "Kalshi HTTP error syncing %s for category %s",
                series_ticker,
                category.slug,
            )
            summary.errors.append({"raw_id": series_ticker, "error": str(exc)})
            if exc.response is not None and exc.response.status_code == 429:
                break
        except Exception:
            logger.exception(
                "Kalshi sync failed for series %s in category %s",
                series_ticker,
                category.slug,
            )

    return summary


def sync_all_category_markets(*, limit=None) -> dict:
    """Sync every canonical category from Polymarket and Kalshi."""
    limit = limit or settings.MARKET_SYNC_CATEGORY_LIMIT
    totals = SyncSummary()
    per_category = {}

    try:
        totals.absorb(sync_top_volume_polymarket_markets())
    except Exception:
        logger.exception("Polymarket top-volume sync failed")

    for category in CANONICAL_CATEGORIES:
        has_poly = bool(category.polymarket_tag)
        has_kalshi = kalshi_enabled() and bool(category.kalshi_series_tickers)
        if not has_poly and not has_kalshi:
            continue
        summary = sync_category_markets(category, limit=limit, kalshi_lightweight=False)
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
    """Refresh open imported markets that have not synced recently."""
    batch_size = batch_size or settings.MARKET_SYNC_STALE_BATCH_SIZE
    stale_minutes = stale_minutes or settings.MARKET_SYNC_STALE_MINUTES
    cutoff = timezone.now() - timezone.timedelta(minutes=stale_minutes)

    refreshed = 0
    failures = 0

    active_sources = [Market.Source.POLYMARKET]
    if kalshi_enabled():
        active_sources.append(Market.Source.KALSHI)

    stale_markets = (
        Market.objects.filter(
            status=Market.Status.OPEN,
            source__in=active_sources,
        )
        .order_by("updated_at")[: batch_size * 3]
    )

    candidates = []
    for market in stale_markets:
        synced_at = market.polymarket_synced_at if market.source == Market.Source.POLYMARKET else market.kalshi_synced_at
        if synced_at is None or synced_at <= cutoff:
            candidates.append(market)
        if len(candidates) >= batch_size:
            break

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
