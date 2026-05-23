"""Celery tasks for background market synchronization."""

import logging

from celery import shared_task
from django.core.cache import cache

from integrations.services import import_markets_from_kalshi
from integrations.sync import refresh_stale_open_markets, sync_all_category_markets, sync_category_markets
from markets.categories import get_category_for_slug

logger = logging.getLogger(__name__)

CATEGORY_SUMMARIES_CACHE_KEY = "landing_category_summaries"


@shared_task(bind=True, ignore_result=True, max_retries=2, default_retry_delay=60)
def sync_category_markets_task(self, category_slug, kalshi_lightweight=True):
    """Background sync for a single browse category."""
    category = get_category_for_slug(category_slug)
    if category is None:
        return
    try:
        sync_category_markets(category, kalshi_lightweight=kalshi_lightweight)
        cache.delete(CATEGORY_SUMMARIES_CACHE_KEY)
    except Exception as exc:
        logger.exception("sync_category_markets_task failed for %s", category_slug)
        raise self.retry(exc=exc) from exc


@shared_task(bind=True, ignore_result=True, max_retries=2, default_retry_delay=60)
def sync_all_category_markets_task(self):
    """Periodic import of category markets from Polymarket and Kalshi."""
    try:
        result = sync_all_category_markets()
        cache.delete(CATEGORY_SUMMARIES_CACHE_KEY)
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


@shared_task(bind=True, ignore_result=True, max_retries=2, default_retry_delay=60)
def import_kalshi_open_markets_task(self):
    """Discover newly listed open Kalshi markets."""
    try:
        from django.conf import settings

        result = import_markets_from_kalshi(
            limit=settings.KALSHI_SYNC_OPEN_LIMIT,
            status="open",
            exclude_mve=True,
        )
        cache.delete(CATEGORY_SUMMARIES_CACHE_KEY)
        created = sum(1 for item in result["imported"] if item["created"])
        logger.info(
            "import_kalshi_open_markets_task finished: total=%s created=%s errors=%s",
            len(result["imported"]),
            created,
            len(result["errors"]),
        )
    except Exception as exc:
        logger.exception("import_kalshi_open_markets_task failed")
        raise self.retry(exc=exc) from exc
