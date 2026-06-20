"""Email and login-modal alerts when a weekly contest week ends."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext as _

from reputation.models import WeeklyContestWinner
from reputation.weekly_contest_services import week_date_range, weekly_contest_enabled

logger = logging.getLogger(__name__)

WEEKLY_CONTEST_WIN_SESSION_KEY = "weekly_contest_win_modal"
WEEKLY_CONTEST_WIN_PENDING_CACHE = "weekly_contest_win_pending:{user_id}"


def _pending_wins_cache_key(user_id):
    return WEEKLY_CONTEST_WIN_PENDING_CACHE.format(user_id=user_id)


def weekly_contest_winner_emails_enabled():
    return bool(getattr(settings, "WEEKLY_CONTEST_WINNER_EMAILS_ENABLED", True))


def user_has_pending_weekly_contest_win(user):
    from django.core.cache import cache

    if not user or not user.is_authenticated:
        return False
    return bool(cache.get(_pending_wins_cache_key(user.id)))


def _append_pending_win(*, user_id, win_id):
    from django.core.cache import cache

    key = _pending_wins_cache_key(user_id)
    pending = list(cache.get(key) or [])
    if win_id not in pending:
        pending.append(win_id)
        cache.set(key, pending, timeout=60 * 60 * 24 * 30)


def queue_weekly_contest_win_on_login(*, request):
    """Move cached winner alerts into the session for the next page load."""
    if not weekly_contest_enabled():
        return
    if not request.user.is_authenticated:
        return

    from django.core.cache import cache

    key = _pending_wins_cache_key(request.user.id)
    pending = cache.get(key)
    if not pending:
        return
    request.session[WEEKLY_CONTEST_WIN_SESSION_KEY] = pending
    cache.delete(key)


def consume_weekly_contest_win_modal(*, request):
    """Return winner modal context once after login, if queued."""
    if not weekly_contest_enabled():
        return None
    if not request.user.is_authenticated:
        return None

    win_ids = request.session.pop(WEEKLY_CONTEST_WIN_SESSION_KEY, None)
    if not win_ids:
        return None

    wins = list(
        WeeklyContestWinner.objects.filter(user=request.user, pk__in=win_ids).order_by(
            "prize_type"
        )
    )
    if not wins:
        return None

    week_code = wins[0].week_code
    since, until = week_date_range(week_code)
    return {
        "wins": wins,
        "week_code": week_code,
        "week_start": since,
        "week_end": until - timedelta(seconds=1),
        "total_prize_usd": sum(win.prize_usd for win in wins),
        "earnings_url_name": "accounts:profile_contest_earnings",
    }


def _prize_type_label(prize_type):
    if prize_type == WeeklyContestWinner.PrizeType.ABSOLUTE:
        return _("Absolute reputation leader")
    return _("Best rep / forecast average")


def send_weekly_contest_winner_email(*, win: WeeklyContestWinner) -> bool:
    if not weekly_contest_winner_emails_enabled():
        return False

    user = win.user
    email = (user.email or "").strip()
    if not email:
        return False

    from django.urls import reverse

    from accounts.email_services import EmailDeliveryError, _send, absolute_url

    week_code = win.week_code
    since, until = week_date_range(week_code)
    earnings_path = reverse(
        "accounts:profile_contest_earnings",
        kwargs={"username": user.username},
    )
    context = {
        "recipient": user,
        "win": win,
        "prize_type_label": _prize_type_label(win.prize_type),
        "week_code": week_code,
        "week_start": since,
        "week_end": until - timedelta(seconds=1),
        "earnings_url": absolute_url(earnings_path),
    }
    try:
        _send(
            subject=lambda: _("You won the weekly contest!"),
            recipient_email=email,
            template_base="weekly_contest_winner",
            context=context,
        )
    except EmailDeliveryError:
        logger.exception("Weekly contest winner email failed for user_id=%s", user.id)
        return False
    return True


def notify_weekly_contest_winners(wins):
    """Email winners and queue login modals. Idempotent via ``notified_at``."""
    if not wins:
        return 0

    notified = 0
    now = timezone.now()
    for win in wins:
        if win.notified_at is not None:
            continue
        send_weekly_contest_winner_email(win=win)
        _append_pending_win(user_id=win.user_id, win_id=win.id)
        win.notified_at = now
        win.save(update_fields=["notified_at"])
        notified += 1
    return notified
