"""Template context for notification badge in navigation."""

from accounts.nav_cache import get_cached_unread_notification_count
from accounts.notification_services import consume_login_notification_toast


def notification_context(request):
    if request.user.is_authenticated:
        return {
            "unread_notification_count": get_cached_unread_notification_count(user=request.user),
            "login_notification_toast": consume_login_notification_toast(request=request),
        }
    return {
        "unread_notification_count": 0,
        "login_notification_toast": None,
    }
