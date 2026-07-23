"""Background maintenance tasks for imported markets."""

import logging

from celery import shared_task
from django.conf import settings

from markets.cleanup_services import run_orphan_resolved_cleanup
from markets.db_maintenance import (
    maybe_vacuum_after_orphan_cleanup,
    report_storage_pressure_if_needed,
    vacuum_markets_market,
)
from markets.prune_services import DEFAULT_PRUNE_STATUSES, run_market_raw_prune

logger = logging.getLogger(__name__)


@shared_task(bind=True, ignore_result=True, max_retries=1, default_retry_delay=300)
def prune_market_raw_fifo_task(self):
    """Compact Polymarket payloads on resolved/closed markets (FIFO)."""
    if not getattr(settings, "MARKET_RAW_PRUNE_ENABLED", False):
        logger.info("prune_market_raw_fifo_task skipped — MARKET_RAW_PRUNE_ENABLED is False")
        return

    batch_size = max(1, getattr(settings, "MARKET_RAW_PRUNE_BATCH_SIZE", 500))
    max_per_run = max(0, int(getattr(settings, "MARKET_RAW_PRUNE_MAX_PER_RUN", 0) or 0))

    try:
        stats = run_market_raw_prune(
            statuses=list(DEFAULT_PRUNE_STATUSES),
            limit=max_per_run,
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
    report_storage_pressure_if_needed()


@shared_task(bind=True, ignore_result=True, max_retries=1, default_retry_delay=300)
def delete_orphan_resolved_markets_task(self):
    """Delete old resolved markets with no user history (retention policy).

    Drains all eligible orphans each run (batch_size is chunk size only).
    Optionally VACUUMs and reports storage pressure afterward.
    """
    if not getattr(settings, "MARKET_ORPHAN_RESOLVED_CLEANUP_ENABLED", False):
        logger.info(
            "delete_orphan_resolved_markets_task skipped — "
            "MARKET_ORPHAN_RESOLVED_CLEANUP_ENABLED is False"
        )
        return

    retention_days = max(
        0, int(getattr(settings, "MARKET_ORPHAN_RESOLVED_RETENTION_DAYS", 7))
    )
    batch_size = max(
        1, int(getattr(settings, "MARKET_ORPHAN_RESOLVED_CLEANUP_BATCH_SIZE", 500))
    )
    max_per_run = max(
        0, int(getattr(settings, "MARKET_ORPHAN_RESOLVED_CLEANUP_MAX_PER_RUN", 0) or 0)
    )

    try:
        stats = run_orphan_resolved_cleanup(
            older_than_days=retention_days,
            limit=max_per_run,
            batch_size=min(500, batch_size),
            dry_run=False,
            order="fifo",
        )
    except Exception as exc:
        logger.exception("delete_orphan_resolved_markets_task failed")
        raise self.retry(exc=exc) from exc

    logger.info(
        "delete_orphan_resolved_markets_task finished: deleted=%s target=%s "
        "orphans=%s retention_days=%s",
        stats["deleted"],
        stats["target"],
        stats["orphan_total"],
        retention_days,
    )

    try:
        vacuum_stats = maybe_vacuum_after_orphan_cleanup(deleted=stats["deleted"])
        logger.info("post-orphan vacuum: %s", vacuum_stats)
    except Exception:
        logger.exception("post-orphan vacuum failed (cleanup already applied)")

    report_storage_pressure_if_needed()


@shared_task(bind=True, ignore_result=True, max_retries=1, default_retry_delay=300)
def vacuum_markets_market_task(self, full: bool = False):
    """Periodic VACUUM [FULL] ANALYZE on markets_market (Postgres only)."""
    if not getattr(settings, "MARKET_VACUUM_ENABLED", True):
        logger.info("vacuum_markets_market_task skipped — MARKET_VACUUM_ENABLED is False")
        return
    if full and not getattr(settings, "MARKET_VACUUM_FULL_ENABLED", True):
        logger.info(
            "vacuum_markets_market_task skipped FULL — MARKET_VACUUM_FULL_ENABLED is False"
        )
        return

    try:
        result = vacuum_markets_market(full=full)
    except Exception as exc:
        logger.exception("vacuum_markets_market_task failed (full=%s)", full)
        raise self.retry(exc=exc) from exc

    logger.info("vacuum_markets_market_task finished: %s", result)
    report_storage_pressure_if_needed()


@shared_task(bind=True, ignore_result=True, max_retries=0)
def check_market_storage_pressure_task(self):
    """Emit Sentry/log warnings when DB size or orphan backlog is too high."""
    report_storage_pressure_if_needed()
