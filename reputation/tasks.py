"""Reputation Celery tasks."""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def finalize_previous_season_task():
    """Idempotently award permanent badges for the most recently ended season."""
    from django.conf import settings

    if not getattr(settings, "SEASON_AWARDS_ENABLED", False):
        return 0

    from reputation.season_services import finalize_season

    try:
        return finalize_season()
    except Exception:  # pragma: no cover - never break the beat schedule
        logger.exception("Season finalization failed")
        return 0


@shared_task(ignore_result=True)
def finalize_previous_weekly_contest_task():
    """Idempotently record winners for the most recently ended calendar week."""
    from django.conf import settings

    if not getattr(settings, "WEEKLY_CONTEST_ENABLED", False):
        return 0

    from reputation.weekly_contest_services import finalize_weekly_contest

    try:
        return finalize_weekly_contest()
    except Exception:  # pragma: no cover - never break the beat schedule
        logger.exception("Weekly contest finalization failed")
        return 0
