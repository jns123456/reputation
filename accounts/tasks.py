"""Celery tasks for outbound engagement email.

Thin wrappers around ``accounts.email_services`` so the business logic stays
synchronous and unit-testable without a broker.
"""

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def send_notification_email_task(notification_id):
    from accounts.email_services import send_notification_email

    return send_notification_email(notification_id)


@shared_task(ignore_result=True)
def send_web_push_task(notification_id):
    from accounts.push_services import send_push_for_notification

    return send_push_for_notification(notification_id)


@shared_task(ignore_result=True)
def send_daily_digest_task():
    """Fan out per-user digest sends to users who opted into email."""
    from accounts.models import NotificationPreference

    recipient_ids = NotificationPreference.objects.filter(
        notify_email=True,
        user__email__gt="",
    ).values_list("user_id", flat=True)

    count = 0
    for user_id in recipient_ids:
        send_user_daily_digest_task.delay(user_id)
        count += 1
    return count


@shared_task(ignore_result=True)
def send_user_daily_digest_task(user_id):
    from accounts.email_services import send_daily_digest

    return send_daily_digest(user_id)


@shared_task(ignore_result=True)
def send_market_resolving_reminders_task(within_hours=24):
    """Nudge users with open forecasts on markets that close within the window."""
    from accounts.notification_services import notify_market_resolving
    from markets.selectors import get_markets_resolving_soon

    notified = 0
    for market in get_markets_resolving_soon(within_hours=within_hours, limit=200):
        try:
            notified += len(notify_market_resolving(market=market))
        except Exception:  # pragma: no cover - one bad market must not stop the batch
            logger.warning("market resolving reminder failed for market_id=%s", market.id, exc_info=True)
    return notified


@shared_task(ignore_result=True)
def send_streak_risk_reminders_task():
    """Email users whose active streak will break tonight unless they engage."""
    from accounts.email_services import send_streak_risk_reminder
    from accounts.streak_services import get_streaks_at_risk, mark_risk_notified

    sent = 0
    for streak in get_streaks_at_risk():
        try:
            if send_streak_risk_reminder(streak):
                sent += 1
            mark_risk_notified(streak)
        except Exception:  # pragma: no cover - one bad recipient must not stop the batch
            logger.warning("streak risk reminder failed for user_id=%s", streak.user_id, exc_info=True)
    return sent
