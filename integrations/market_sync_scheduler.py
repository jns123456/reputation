"""Periodic Polymarket sync for single-dyno deployments (e.g. Heroku Eco without Celery worker)."""

from __future__ import annotations

import logging
import threading
import time

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

LAST_FULL_SYNC_KEY = "market_sync:last_full_run_epoch"
FULL_SYNC_LOCK_KEY = "market_sync:full_sync_lock"
CATEGORY_SUMMARIES_CACHE_KEY = "landing_category_summaries"

_scheduler_started = False
_start_lock = threading.Lock()


def full_sync_interval_seconds() -> int:
    hours = getattr(settings, "MARKET_FULL_SYNC_INTERVAL_HOURS", 6)
    return max(1, hours) * 3600


def is_full_sync_due() -> bool:
    last_run = cache.get(LAST_FULL_SYNC_KEY)
    if last_run is None:
        return True
    return (time.time() - float(last_run)) >= full_sync_interval_seconds()


def record_full_sync_run() -> None:
    cache.set(LAST_FULL_SYNC_KEY, time.time(), timeout=None)


def run_scheduled_market_sync(*, force: bool = False) -> dict | None:
    """
    Run category import + stale refresh when the interval has elapsed.
    Uses a cache lock so concurrent workers only run one sync at a time.
    """
    if not force and not is_full_sync_due():
        logger.debug("Scheduled market sync skipped; not due yet")
        return None

    lock_timeout = max(full_sync_interval_seconds(), 3600)
    if not cache.add(FULL_SYNC_LOCK_KEY, True, timeout=lock_timeout):
        logger.debug("Scheduled market sync skipped; another worker is running")
        return None

    from integrations.sync import refresh_stale_open_markets, sync_all_category_markets

    try:
        logger.info("Starting scheduled Polymarket market sync")
        category_result = sync_all_category_markets(
            limit=getattr(settings, "MARKET_SYNC_CATEGORY_LIMIT", 48)
        )
        stale_result = refresh_stale_open_markets()
        record_full_sync_run()
        cache.delete(CATEGORY_SUMMARIES_CACHE_KEY)
        summary = {
            "categories": category_result,
            "stale": stale_result,
        }
        logger.info(
            "Scheduled market sync finished: imported=%s updated=%s stale_refreshed=%s",
            category_result["imported"],
            category_result["updated"],
            stale_result["refreshed"],
        )
        return summary
    finally:
        cache.delete(FULL_SYNC_LOCK_KEY)


def _sync_loop() -> None:
    while True:
        try:
            run_scheduled_market_sync()
        except Exception:
            logger.exception("Embedded market sync loop failed")
        time.sleep(full_sync_interval_seconds())


def start_embedded_market_sync_scheduler() -> None:
    """Start a daemon thread that syncs markets every MARKET_FULL_SYNC_INTERVAL_HOURS."""
    global _scheduler_started

    if not getattr(settings, "ENABLE_EMBEDDED_MARKET_SYNC", False):
        return

    with _start_lock:
        if _scheduler_started:
            return
        _scheduler_started = True

    thread = threading.Thread(
        target=_sync_loop,
        name="market-sync-scheduler",
        daemon=True,
    )
    thread.start()
    logger.info(
        "Embedded market sync scheduler started (every %s hours)",
        getattr(settings, "MARKET_FULL_SYNC_INTERVAL_HOURS", 6),
    )
