"""Template context for notification badge in navigation."""

from accounts.notification_selectors import get_recent_notifications
from accounts.notification_services import (
    consume_login_notification_toast,
    get_unread_notification_count,
)


def notification_context(request):
    if request.user.is_authenticated:
        return {
            "unread_notification_count": get_unread_notification_count(user=request.user),
            "recent_notifications": get_recent_notifications(user=request.user, limit=8),
            "login_notification_toast": consume_login_notification_toast(request=request),
        }
    return {
        "unread_notification_count": 0,
        "recent_notifications": [],
        "login_notification_toast": None,
    }
