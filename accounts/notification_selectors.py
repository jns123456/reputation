"""Notification read queries."""

from accounts.models import Notification

NOTIFICATION_SELECT_RELATED = (
    "actor",
    "prediction",
    "prediction__market",
    "comment",
    "comment__market",
    "reputation_event",
    "challenge",
    "challenge__winner",
    "market",
    "pulse_post",
    "pulse_comment",
    "pulse_comment__post",
)


def get_user_notifications(*, user, limit=50):
    return (
        Notification.objects.filter(recipient=user)
        .select_related(*NOTIFICATION_SELECT_RELATED)
        .order_by("-created_at")[:limit]
    )


def get_recent_notifications(*, user, limit=8):
    return get_user_notifications(user=user, limit=limit)


def get_unread_recent_notifications(*, user, limit=5):
    return (
        Notification.objects.filter(recipient=user, read_at__isnull=True)
        .select_related(*NOTIFICATION_SELECT_RELATED)
        .order_by("-created_at")[:limit]
    )
