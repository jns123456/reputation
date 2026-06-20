"""Template context for notification badge and streak in navigation."""

from django.conf import settings

from accounts.nav_cache import (
    get_cached_display_streak,
    get_cached_unread_notification_count,
)
from messaging.nav_cache import get_cached_unread_dm_count
from accounts.notification_services import consume_login_notification_toast
from reputation.weekly_contest_services import consume_weekly_contest_announcement
from reputation.weekly_contest_winner_notifications import (
    consume_weekly_contest_win_modal,
    queue_weekly_contest_win_on_login,
)


def notification_context(request):
    if request.user.is_authenticated:
        queue_weekly_contest_win_on_login(request=request)
        weekly_contest_win_modal = consume_weekly_contest_win_modal(request=request)
        weekly_contest_announcement = (
            None
            if weekly_contest_win_modal
            else consume_weekly_contest_announcement(request=request)
        )
        return {
            "unread_notification_count": get_cached_unread_notification_count(user=request.user),
            "unread_dm_count": get_cached_unread_dm_count(user=request.user),
            "login_notification_toast": consume_login_notification_toast(request=request),
            "weekly_contest_announcement": weekly_contest_announcement,
            "weekly_contest_win_modal": weekly_contest_win_modal,
            "nav_streak_days": get_cached_display_streak(user=request.user),
        }
    return {
        "unread_notification_count": 0,
        "unread_dm_count": 0,
        "login_notification_toast": None,
        "weekly_contest_announcement": None,
        "weekly_contest_win_modal": None,
        "nav_streak_days": 0,
    }


def auth0_context(request):
    """Expose whether the Auth0 login option is configured."""
    return {
        "auth0_enabled": settings.AUTH0_ENABLED,
        "auth0_google_connection": settings.AUTH0_GOOGLE_CONNECTION,
        "turnstile_site_key": getattr(settings, "TURNSTILE_SITE_KEY", ""),
    }
