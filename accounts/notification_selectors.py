"""Notification read queries."""

from accounts.models import Notification


def get_user_notifications(*, user, limit=50):
    return (
        Notification.objects.filter(recipient=user)
        .select_related(
            "actor",
            "prediction",
            "prediction__market",
            "comment",
            "comment__market",
            "reputation_event",
        )
        .order_by("-created_at")[:limit]
    )


def get_recent_notifications(*, user, limit=8):
    return get_user_notifications(user=user, limit=limit)


def get_unread_recent_notifications(*, user, limit=5):
    return (
        Notification.objects.filter(recipient=user, read_at__isnull=True)
        .select_related(
            "actor",
            "prediction",
            "prediction__market",
            "comment",
            "comment__market",
            "reputation_event",
        )
        .order_by("-created_at")[:limit]
    )
