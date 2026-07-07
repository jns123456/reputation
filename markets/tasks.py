"""Background maintenance tasks for imported markets."""

import logging

from celery import shared_task
from django.conf import settings

from markets.prune_services import DEFAULT_PRUNE_STATUSES, run_market_raw_prune

logger = logging.getLogger(__name__)


@shared_task(bind=True, ignore_result=True, max_retries=1, default_retry_delay=300)
def prune_market_raw_fifo_task(self):
    """Compact oldest resolved/closed Polymarket payloads (FIFO batch)."""
    if not getattr(settings, "MARKET_RAW_PRUNE_ENABLED", False):
        logger.info("prune_market_raw_fifo_task skipped — MARKET_RAW_PRUNE_ENABLED is False")
        return

    batch_size = max(1, getattr(settings, "MARKET_RAW_PRUNE_BATCH_SIZE", 500))

    try:
        stats = run_market_raw_prune(
            statuses=list(DEFAULT_PRUNE_STATUSES),
            limit=batch_size,
            batch_size=min(500, batch_size),
            dry_run=False,
            order="fifo",
        )
    except Exception as exc:
        logger.exception("prune_market_raw_fifo_task failed")
        raise self.retry(exc=exc) from exc

    saved = stats["bytes_before"] - stats["bytes_after"]
    logger.info(
        "prune_market_raw_fifo_task finished: pending=%s updated=%s examined=%s saved_bytes=%s",
        stats["pending"],
        stats["updated"],
        stats["examined"],
        saved,
    )
