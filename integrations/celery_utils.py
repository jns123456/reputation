"""Helpers for enqueueing background sync without blocking HTTP requests."""

import logging
import socket
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


def safe_cache_delete(key: str) -> bool:
    """Delete a cache key, swallowing backend (Redis) connection errors.

    Cache invalidation is best-effort: a transient Redis outage must never fail
    or retry the surrounding task, which already did its real work. Returns True
    on success, False when the delete could not be performed.
    """
    try:
        cache.delete(key)
        return True
    except Exception:
        logger.warning("Cache delete failed for %s; continuing", key, exc_info=True)
        return False


CELERY_BROKER_AVAILABLE_CACHE_KEY = "celery_broker_available"
CELERY_BROKER_CHECK_SECONDS = 60
MARKET_REFRESH_ENQUEUE_PREFIX = "market_refresh_queued:"
MARKET_REFRESH_ENQUEUE_SECONDS = 300


def celery_broker_available(*, force_check=False) -> bool:
    """Fast check whether the Celery broker accepts connections."""
    if not force_check:
        cached = cache.get(CELERY_BROKER_AVAILABLE_CACHE_KEY)
        if cached is not None:
            return cached

    available = False
    try:
        parsed = urlparse(settings.CELERY_BROKER_URL)
        host = parsed.hostname or "localhost"
        port = parsed.port or 6379
        with socket.create_connection((host, port), timeout=0.05):
            available = True
    except OSError:
        available = False

    cache.set(CELERY_BROKER_AVAILABLE_CACHE_KEY, available, CELERY_BROKER_CHECK_SECONDS)
    return available


def enqueue_category_sync(category_slug: str) -> bool:
    """Queue a category sync task when the broker is reachable."""
    if not celery_broker_available():
        logger.debug("Skipping category sync enqueue; Celery broker unavailable")
        return False

    from integrations.tasks import sync_category_markets_task

    try:
        sync_category_markets_task.delay(category_slug)
    except Exception:
        cache.set(CELERY_BROKER_AVAILABLE_CACHE_KEY, False, CELERY_BROKER_CHECK_SECONDS)
        logger.exception("Failed to enqueue category sync for %s", category_slug)
        return False

    return True


def market_is_stale(market) -> bool:
    """True when an imported open market has not synced recently."""
    from markets.models import Market

    if market.source != Market.Source.POLYMARKET:
        return False
    if market.status != Market.Status.OPEN:
        return False

    stale_minutes = getattr(settings, "MARKET_SYNC_STALE_MINUTES", 30)
    cutoff = timezone.now() - timezone.timedelta(minutes=stale_minutes)
    synced_at = market.polymarket_synced_at
    return synced_at is None or synced_at <= cutoff


def enqueue_market_refresh_if_stale(market) -> bool:
    """Queue a single-market refresh without blocking the HTTP response."""
    if not market_is_stale(market):
        return False

    cache_key = f"{MARKET_REFRESH_ENQUEUE_PREFIX}{market.pk}"
    if cache.get(cache_key):
        return False

    if not celery_broker_available():
        logger.debug("Skipping market refresh enqueue; Celery broker unavailable")
        return False

    from integrations.tasks import refresh_market_task

    try:
        refresh_market_task.delay(market.pk)
    except Exception:
        cache.set(CELERY_BROKER_AVAILABLE_CACHE_KEY, False, CELERY_BROKER_CHECK_SECONDS)
        logger.exception("Failed to enqueue market refresh for %s", market.pk)
        return False

    cache.set(cache_key, True, MARKET_REFRESH_ENQUEUE_SECONDS)
    return True
