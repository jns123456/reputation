"""Periodic Polymarket sync for single-dyno deployments (e.g. Heroku Eco without Celery worker)."""

from __future__ import annotations

import logging
import threading
import time

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

LAST_FULL_SYNC_KEY = "market_sync:last_full_run_epoch"
LAST_STALE_SYNC_KEY = "market_sync:last_stale_run_epoch"
FULL_SYNC_LOCK_KEY = "market_sync:full_sync_lock"
STALE_SYNC_LOCK_KEY = "market_sync:stale_sync_lock"
CATEGORY_SUMMARIES_CACHE_KEY = "landing_category_summaries"

_scheduler_started = False
_start_lock = threading.Lock()


def full_sync_interval_seconds() -> int:
    hours = getattr(settings, "MARKET_FULL_SYNC_INTERVAL_HOURS", 6)
    return max(1, hours) * 3600


def stale_sync_interval_seconds() -> int:
    minutes = getattr(settings, "MARKET_STALE_SYNC_INTERVAL_MINUTES", 10)
    return max(1, minutes) * 60


def is_full_sync_due() -> bool:
    last_run = cache.get(LAST_FULL_SYNC_KEY)
    if last_run is None:
        return True
    return (time.time() - float(last_run)) >= full_sync_interval_seconds()


def is_stale_sync_due() -> bool:
    last_run = cache.get(LAST_STALE_SYNC_KEY)
    if last_run is None:
        return True
    return (time.time() - float(last_run)) >= stale_sync_interval_seconds()


def record_full_sync_run() -> None:
    cache.set(LAST_FULL_SYNC_KEY, time.time(), timeout=None)


def record_stale_sync_run() -> None:
    cache.set(LAST_STALE_SYNC_KEY, time.time(), timeout=None)


def run_stale_market_refresh(*, force: bool = False) -> dict | None:
    """Refresh stale/elapsed open markets on a short cadence."""
    if not force and not is_stale_sync_due():
        logger.debug("Stale market refresh skipped; not due yet")
        return None

    lock_timeout = max(stale_sync_interval_seconds(), 300)
    if not cache.add(STALE_SYNC_LOCK_KEY, True, timeout=lock_timeout):
        logger.debug("Stale market refresh skipped; another worker is running")
        return None

    from integrations.sync import refresh_stale_open_markets

    try:
        result = refresh_stale_open_markets()
        record_stale_sync_run()
        logger.info(
            "Stale market refresh finished: refreshed=%s failures=%s",
            result["refreshed"],
            result["failures"],
        )
        return result
    finally:
        cache.delete(STALE_SYNC_LOCK_KEY)


def run_scheduled_market_sync(*, force: bool = False) -> dict | None:
    """
    Run category import and/or stale refresh when their intervals have elapsed.
    Uses a cache lock so concurrent workers only run one sync at a time.
    """
    full_due = force or is_full_sync_due()
    stale_due = force or is_stale_sync_due()
    if not full_due and not stale_due:
        logger.debug("Scheduled market sync skipped; nothing due yet")
        return None

    category_result = None
    stale_result = None

    if full_due:
        lock_timeout = max(full_sync_interval_seconds(), 3600)
        if not cache.add(FULL_SYNC_LOCK_KEY, True, timeout=lock_timeout):
            logger.debug("Full market sync skipped; another worker is running")
        else:
            from integrations.sync import sync_all_category_markets

            try:
                logger.info("Starting scheduled Polymarket category sync")
                print("Starting scheduled Polymarket category sync", flush=True)
                category_result = sync_all_category_markets(
                    limit=getattr(settings, "MARKET_SYNC_CATEGORY_LIMIT", 48)
                )
                record_full_sync_run()
                cache.delete(CATEGORY_SUMMARIES_CACHE_KEY)
            finally:
                cache.delete(FULL_SYNC_LOCK_KEY)

    if stale_due:
        stale_result = run_stale_market_refresh(force=True)

    summary = {
        "categories": category_result,
        "stale": stale_result,
    }
    logger.info(
        "Scheduled market sync finished: imported=%s updated=%s stale_refreshed=%s",
        category_result["imported"] if category_result else 0,
        category_result["updated"] if category_result else 0,
        stale_result["refreshed"] if stale_result else 0,
    )
    print(
        "Scheduled market sync finished: "
        f"imported={category_result['imported'] if category_result else 0} "
        f"updated={category_result['updated'] if category_result else 0} "
        f"stale={stale_result['refreshed'] if stale_result else 0}",
        flush=True,
    )
    return summary


def _sync_loop() -> None:
    while True:
        try:
            run_scheduled_market_sync()
        except Exception:
            logger.exception("Embedded market sync loop failed")
        time.sleep(min(full_sync_interval_seconds(), stale_sync_interval_seconds()))


def start_embedded_market_sync_scheduler() -> None:
    """Start a daemon thread that runs full/stale market sync cadences."""
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
        "Embedded market sync scheduler started (full=%s hours, stale=%s minutes)",
        getattr(settings, "MARKET_FULL_SYNC_INTERVAL_HOURS", 6),
        getattr(settings, "MARKET_STALE_SYNC_INTERVAL_MINUTES", 10),
    )
    print(
        "Embedded market sync scheduler started "
        f"(full every {getattr(settings, 'MARKET_FULL_SYNC_INTERVAL_HOURS', 6)}h, "
        f"stale every {getattr(settings, 'MARKET_STALE_SYNC_INTERVAL_MINUTES', 10)}m)",
        flush=True,
    )
