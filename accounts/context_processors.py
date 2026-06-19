"""Template context for notification badge and streak in navigation."""

from django.conf import settings

from accounts.nav_cache import (
    get_cached_display_streak,
    get_cached_unread_notification_count,
)
from accounts.notification_services import consume_login_notification_toast
from reputation.weekly_contest_services import consume_weekly_contest_announcement


def notification_context(request):
    if request.user.is_authenticated:
        return {
            "unread_notification_count": get_cached_unread_notification_count(user=request.user),
            "login_notification_toast": consume_login_notification_toast(request=request),
            "weekly_contest_announcement": consume_weekly_contest_announcement(request=request),
            "nav_streak_days": get_cached_display_streak(user=request.user),
        }
    return {
        "unread_notification_count": 0,
        "login_notification_toast": None,
        "weekly_contest_announcement": None,
        "nav_streak_days": 0,
    }


def auth0_context(request):
    """Expose whether the Auth0 login option is configured."""
    return {
        "auth0_enabled": settings.AUTH0_ENABLED,
        "auth0_google_connection": settings.AUTH0_GOOGLE_CONNECTION,
        "turnstile_site_key": getattr(settings, "TURNSTILE_SITE_KEY", ""),
    }
