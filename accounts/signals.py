import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import (
    ActivityStreak,
    Notification,
    NotificationPreference,
    User,
    UserProfile,
)

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)
        NotificationPreference.objects.create(user=instance)
        ActivityStreak.objects.create(user=instance)


@receiver(post_save, sender=Notification)
def enqueue_notification_email(sender, instance, created, **kwargs):
    """Mirror new in-app notifications to email (the external trigger)."""
    if not created:
        return

    notification_id = instance.id

    def _enqueue():
        try:
            from accounts.tasks import send_notification_email_task

            send_notification_email_task.delay(notification_id)
        except Exception:  # pragma: no cover - broker may be unavailable in dev/tests
            logger.warning(
                "Could not enqueue notification email id=%s", notification_id, exc_info=True
            )

        try:
            from django.conf import settings

            if getattr(settings, "WEBPUSH_ENABLED", False):
                from accounts.tasks import send_web_push_task

                send_web_push_task.delay(notification_id)
        except Exception:  # pragma: no cover - broker may be unavailable in dev/tests
            logger.warning(
                "Could not enqueue web push id=%s", notification_id, exc_info=True
            )

    transaction.on_commit(_enqueue)
