"""Delete inactive resolved markets that have no user history.

Keeps any market referenced by predictions, comments, challenges, watches, or
notifications. Resolved prediction history remains immutable (AGENTS.md §6).
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Exists, OuterRef
from django.db.models.functions import Coalesce
from django.utils import timezone

from markets.models import Market

ORDER_FIFO = "fifo"
ORDER_PK = "pk"
VALID_DELETE_ORDERS = frozenset({ORDER_FIFO, ORDER_PK})


def parse_delete_order(value: str) -> str:
    order = (value or ORDER_FIFO).strip().lower()
    if order not in VALID_DELETE_ORDERS:
        raise ValueError(
            f"Invalid order {order!r}. Choose from: {', '.join(sorted(VALID_DELETE_ORDERS))}."
        )
    return order


def orphan_resolved_market_queryset(*, older_than_days: int | None = None):
    """Resolved markets with no forecasts, discussion, challenges, or watches."""
    from accounts.models import MarketWatch, Notification
    from challenges.models import ChallengeMarket
    from comments.models import Comment
    from predictions.models import Prediction

    qs = Market.objects.filter(status=Market.Status.RESOLVED).annotate(
        _has_prediction=Exists(
            Prediction.objects.filter(market_id=OuterRef("pk"))
        ),
        _has_comment=Exists(Comment.objects.filter(market_id=OuterRef("pk"))),
        _has_challenge=Exists(
            ChallengeMarket.objects.filter(market_id=OuterRef("pk"))
        ),
        _has_watch=Exists(MarketWatch.objects.filter(market_id=OuterRef("pk"))),
        _has_notification=Exists(
            Notification.objects.filter(market_id=OuterRef("pk"))
        ),
    ).filter(
        _has_prediction=False,
        _has_comment=False,
        _has_challenge=False,
        _has_watch=False,
        _has_notification=False,
    )

    if older_than_days is not None:
        days = max(0, int(older_than_days))
        cutoff = timezone.now() - timedelta(days=days)
        qs = qs.annotate(
            _inactive_at=Coalesce(
                "resolution_date",
                "close_date",
                "updated_at",
                "created_at",
            )
        ).filter(_inactive_at__lte=cutoff)

    return qs


def orphan_resolved_market_candidates(*, older_than_days: int | None = None, order: str = ORDER_FIFO):
    order = parse_delete_order(order)
    qs = orphan_resolved_market_queryset(older_than_days=older_than_days)
    if order == ORDER_FIFO:
        return qs.annotate(
            _delete_sort_at=Coalesce(
                "resolution_date",
                "close_date",
                "updated_at",
                "created_at",
            )
        ).order_by("_delete_sort_at", "pk")
    return qs.order_by("pk")


def empty_cleanup_stats() -> dict:
    return {
        "resolved_total": 0,
        "orphan_total": 0,
        "target": 0,
        "deleted": 0,
        "dry_run": False,
    }


def resolve_delete_target(
    *,
    orphan_total: int,
    resolved_total: int,
    limit: int = 0,
    min_fraction_of_resolved: float = 0.0,
) -> int:
    """How many orphan rows to delete this run."""
    if orphan_total <= 0:
        return 0

    if min_fraction_of_resolved > 0 and resolved_total > 0:
        floor = int(resolved_total * min_fraction_of_resolved)
        target = min(orphan_total, max(floor, 0))
    else:
        target = orphan_total

    if limit and limit > 0:
        target = min(target, limit)

    return max(0, target)


def run_orphan_resolved_cleanup(
    *,
    older_than_days: int | None = None,
    limit: int = 0,
    min_fraction_of_resolved: float = 0.0,
    batch_size: int = 500,
    order: str = ORDER_FIFO,
    dry_run: bool = False,
) -> dict:
    """Delete inactive resolved markets. Never touches rows with user history."""
    batch_size = max(1, batch_size)
    resolved_total = Market.objects.filter(status=Market.Status.RESOLVED).count()
    candidates = orphan_resolved_market_candidates(
        older_than_days=older_than_days,
        order=order,
    )
    orphan_total = candidates.count()
    target = resolve_delete_target(
        orphan_total=orphan_total,
        resolved_total=resolved_total,
        limit=limit,
        min_fraction_of_resolved=min_fraction_of_resolved,
    )

    stats = empty_cleanup_stats()
    stats.update(
        {
            "resolved_total": resolved_total,
            "orphan_total": orphan_total,
            "target": target,
            "dry_run": dry_run,
        }
    )
    if target <= 0:
        return stats

    deleted = 0
    while deleted < target:
        chunk = list(
            candidates.values_list("pk", flat=True)[: min(batch_size, target - deleted)]
        )
        if not chunk:
            break
        if dry_run:
            deleted += len(chunk)
            candidates = candidates.exclude(pk__in=chunk)
            continue
        Market.objects.filter(pk__in=chunk).delete()
        deleted += len(chunk)

    stats["deleted"] = deleted
    return stats


def maybe_compact_resolved_market_raw(market) -> bool:
    """Shrink Polymarket JSON once a market is resolved. Returns True if saved."""
    from markets.prune_services import (
        compact_polymarket_raw_payloads,
        market_raw_needs_pruning,
    )

    if market.status != Market.Status.RESOLVED:
        return False
    if not market_raw_needs_pruning(market):
        return False

    new_raw, new_event = compact_polymarket_raw_payloads(market)
    market.polymarket_raw = new_raw
    market.polymarket_event_raw = new_event
    market.save(
        update_fields=["polymarket_raw", "polymarket_event_raw", "updated_at"]
    )
    return True
