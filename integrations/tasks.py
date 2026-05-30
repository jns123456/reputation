"""Celery tasks for background market synchronization."""

import logging

from celery import shared_task

from integrations.celery_utils import safe_cache_delete
from integrations.sync import refresh_stale_open_markets, sync_all_category_markets, sync_category_markets
from markets.categories import get_category_for_slug

logger = logging.getLogger(__name__)

CATEGORY_SUMMARIES_CACHE_KEY = "landing_category_summaries"


@shared_task(bind=True, ignore_result=True, max_retries=2, default_retry_delay=60)
def sync_world_cup_match_markets_task(self):
    """Background import of FIFA World Cup 3-way match markets."""
    from integrations.services import sync_world_cup_match_markets

    try:
        result = sync_world_cup_match_markets()
        safe_cache_delete(CATEGORY_SUMMARIES_CACHE_KEY)
        logger.info(
            "sync_world_cup_match_markets_task finished: imported=%s errors=%s",
            len(result["imported"]),
            len(result["errors"]),
        )
    except Exception as exc:
        logger.exception("sync_world_cup_match_markets_task failed")
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, ignore_result=True, max_retries=2, default_retry_delay=60)
def sync_category_markets_task(self, category_slug):
    """Background sync for a single browse category."""
    category = get_category_for_slug(category_slug)
    if category is None:
        return
    try:
        sync_category_markets(category)
        safe_cache_delete(CATEGORY_SUMMARIES_CACHE_KEY)
    except Exception as exc:
        logger.exception("sync_category_markets_task failed for %s", category_slug)
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, ignore_result=True, max_retries=2, default_retry_delay=60)
def sync_all_category_markets_task(self):
    """Periodic import of category markets from Polymarket."""
    try:
        result = sync_all_category_markets()
        safe_cache_delete(CATEGORY_SUMMARIES_CACHE_KEY)
        logger.info(
            "sync_all_category_markets_task finished: imported=%s updated=%s errors=%s",
            result["imported"],
            result["updated"],
            len(result["errors"]),
        )
    except Exception as exc:
        logger.exception("sync_all_category_markets_task failed")
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, ignore_result=True, max_retries=2, default_retry_delay=60)
def refresh_market_task(self, market_id):
    """Background refresh of a single market from its external source."""
    from integrations.sync import refresh_market
    from markets.models import Market

    market = Market.objects.filter(pk=market_id).first()
    if market is None:
        return
    try:
        refresh_market(market)
    except Exception as exc:
        logger.exception("refresh_market_task failed for market %s", market_id)
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, ignore_result=True, max_retries=2, default_retry_delay=60)
def refresh_stale_open_markets_task(self):
    """Periodic refresh of stale open markets from external APIs."""
    try:
        result = refresh_stale_open_markets()
        logger.info(
            "refresh_stale_open_markets_task finished: refreshed=%s failures=%s",
            result["refreshed"],
            result["failures"],
        )
    except Exception as exc:
        logger.exception("refresh_stale_open_markets_task failed")
        raise self.retry(exc=exc) from exc
