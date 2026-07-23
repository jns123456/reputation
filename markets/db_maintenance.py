"""Postgres maintenance helpers for market table disk/RAM pressure.

Keeps Essential-tier DBs bounded after orphan deletes and raw compaction.
No-ops on non-PostgreSQL backends (local SQLite tests).
"""

from __future__ import annotations

import logging
from typing import Any

from django.conf import settings
from django.db import connection

logger = logging.getLogger(__name__)

MARKETS_RELATION = "markets_market"


def _is_postgres() -> bool:
    return connection.vendor == "postgresql"


def get_database_size_bytes() -> int | None:
    if not _is_postgres():
        return None
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_database_size(current_database())")
        row = cursor.fetchone()
    return int(row[0]) if row else None


def get_relation_total_bytes(relation: str = MARKETS_RELATION) -> int | None:
    if not _is_postgres():
        return None
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_total_relation_size(%s::regclass)", [relation])
        row = cursor.fetchone()
    return int(row[0]) if row else None


def vacuum_markets_market(*, full: bool = False) -> dict[str, Any]:
    """Run VACUUM [FULL] ANALYZE on markets_market. Requires autocommit."""
    result = {
        "ran": False,
        "full": full,
        "skipped_reason": "",
        "relation_bytes_after": None,
    }
    if not _is_postgres():
        result["skipped_reason"] = "not_postgresql"
        return result

    sql = (
        f"VACUUM FULL ANALYZE {MARKETS_RELATION}"
        if full
        else f"VACUUM ANALYZE {MARKETS_RELATION}"
    )
    # VACUUM cannot run inside a transaction block.
    connection.set_autocommit(True)
    try:
        with connection.cursor() as cursor:
            cursor.execute(sql)
        result["ran"] = True
        result["relation_bytes_after"] = get_relation_total_bytes()
    except Exception:
        logger.exception("vacuum_markets_market failed (full=%s)", full)
        raise
    return result


def orphan_resolved_count(*, older_than_days: int | None = None) -> int:
    from markets.cleanup_services import orphan_resolved_market_queryset

    return orphan_resolved_market_queryset(older_than_days=older_than_days).count()


def collect_storage_pressure(*, retention_days: int | None = None) -> dict[str, Any]:
    """Snapshot sizes + orphan backlog for alerts / ops logs."""
    if retention_days is None:
        retention_days = int(
            getattr(settings, "MARKET_ORPHAN_RESOLVED_RETENTION_DAYS", 7)
        )
    db_bytes = get_database_size_bytes()
    market_bytes = get_relation_total_bytes()
    orphans = orphan_resolved_count(older_than_days=retention_days)
    return {
        "database_bytes": db_bytes,
        "markets_market_bytes": market_bytes,
        "orphan_resolved_count": orphans,
        "retention_days": retention_days,
    }


def storage_pressure_alerts(snapshot: dict[str, Any]) -> list[str]:
    """Return human-readable alert reasons when thresholds are exceeded."""
    alerts: list[str] = []
    db_limit = int(getattr(settings, "MARKET_STORAGE_ALERT_DB_BYTES", 0) or 0)
    orphan_limit = int(
        getattr(settings, "MARKET_STORAGE_ALERT_ORPHAN_COUNT", 0) or 0
    )
    db_bytes = snapshot.get("database_bytes")
    orphans = int(snapshot.get("orphan_resolved_count") or 0)

    if db_limit > 0 and db_bytes is not None and db_bytes >= db_limit:
        alerts.append(
            f"database_size={db_bytes} exceeds alert threshold={db_limit}"
        )
    if orphan_limit > 0 and orphans >= orphan_limit:
        alerts.append(
            f"orphan_resolved_count={orphans} exceeds alert threshold={orphan_limit}"
        )
    return alerts


def report_storage_pressure_if_needed(
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Log + Sentry-warn when disk/orphan pressure crosses configured limits."""
    if not getattr(settings, "MARKET_STORAGE_ALERT_ENABLED", True):
        return {"enabled": False, "alerts": [], "snapshot": snapshot or {}}

    snap = snapshot or collect_storage_pressure()
    alerts = storage_pressure_alerts(snap)
    if not alerts:
        logger.info(
            "market storage ok: database_bytes=%s markets_market_bytes=%s "
            "orphan_resolved_count=%s",
            snap.get("database_bytes"),
            snap.get("markets_market_bytes"),
            snap.get("orphan_resolved_count"),
        )
        return {"enabled": True, "alerts": [], "snapshot": snap}

    message = "Market storage pressure: " + "; ".join(alerts)
    logger.warning("%s | snapshot=%s", message, snap)
    try:
        import sentry_sdk

        with sentry_sdk.new_scope() as scope:
            scope.set_context("market_storage", {**snap, "alerts": alerts})
            sentry_sdk.capture_message(message, level="warning")
    except Exception:
        logger.exception("Failed to report storage pressure to Sentry")
    return {"enabled": True, "alerts": alerts, "snapshot": snap}


def maybe_vacuum_after_orphan_cleanup(*, deleted: int) -> dict[str, Any]:
    """VACUUM (not FULL) after a sizable orphan delete to reclaim table bloat."""
    min_deleted = int(
        getattr(settings, "MARKET_VACUUM_AFTER_DELETE_MIN", 100) or 0
    )
    if deleted < min_deleted:
        return {
            "ran": False,
            "full": False,
            "skipped_reason": "below_delete_threshold",
            "deleted": deleted,
        }
    if not getattr(settings, "MARKET_VACUUM_ENABLED", True):
        return {
            "ran": False,
            "full": False,
            "skipped_reason": "disabled",
            "deleted": deleted,
        }
    result = vacuum_markets_market(full=False)
    result["deleted"] = deleted
    return result
