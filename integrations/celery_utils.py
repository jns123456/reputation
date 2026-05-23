"""Helpers for enqueueing background sync without blocking HTTP requests."""

import logging
import socket
from urllib.parse import urlparse

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

CELERY_BROKER_AVAILABLE_CACHE_KEY = "celery_broker_available"
CELERY_BROKER_CHECK_SECONDS = 60


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
