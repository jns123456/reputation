"""Template context for notification badge and streak in navigation."""

from accounts.nav_cache import (
    get_cached_display_streak,
    get_cached_unread_notification_count,
)
from accounts.notification_services import consume_login_notification_toast


def notification_context(request):
    if request.user.is_authenticated:
        return {
            "unread_notification_count": get_cached_unread_notification_count(user=request.user),
            "login_notification_toast": consume_login_notification_toast(request=request),
            "nav_streak_days": get_cached_display_streak(user=request.user),
        }
    return {
        "unread_notification_count": 0,
        "login_notification_toast": None,
        "nav_streak_days": 0,
    }
