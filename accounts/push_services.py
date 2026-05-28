"""Web Push delivery — encrypt and POST notifications to browser endpoints.

Inert unless VAPID keys are configured (``settings.WEBPUSH_ENABLED``). Dead
subscriptions (404/410 from the push service) are pruned automatically. Push is
a delivery channel only; it never creates reputation/popularity side effects.
"""

import json
import logging

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def is_enabled():
    return bool(getattr(settings, "WEBPUSH_ENABLED", False))


def get_vapid_public_key():
    raw = (getattr(settings, "VAPID_PUBLIC_KEY", "") or "").strip()
    prefix = "Application Server Key = "
    if raw.startswith(prefix):
        raw = raw[len(prefix) :].strip()
    return raw


def save_subscription(*, user, subscription, user_agent=""):
    """Create/refresh a PushSubscription from a browser subscription payload."""
    from accounts.models import PushSubscription

    endpoint = (subscription or {}).get("endpoint")
    keys = (subscription or {}).get("keys") or {}
    p256dh = keys.get("p256dh")
    auth = keys.get("auth")
    if not endpoint or not p256dh or not auth:
        raise ValueError("Invalid push subscription payload.")

    obj, _created = PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "user": user,
            "p256dh": p256dh,
            "auth": auth,
            "user_agent": (user_agent or "")[:300],
        },
    )
    return obj


def delete_subscription(*, user, endpoint):
    from accounts.models import PushSubscription

    if not endpoint:
        return 0
    deleted, _ = PushSubscription.objects.filter(user=user, endpoint=endpoint).delete()
    return deleted


def _send_one(subscription, payload):
    """Send to a single PushSubscription. Returns True if delivered, False if dead."""
    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info=subscription.as_subscription_info(),
            data=json.dumps(payload),
            vapid_private_key=settings.VAPID_PRIVATE_KEY,
            vapid_claims={"sub": settings.VAPID_CLAIMS_EMAIL},
            timeout=10,
        )
        subscription.last_used_at = timezone.now()
        subscription.save(update_fields=["last_used_at"])
        return True
    except WebPushException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (404, 410):
            # Endpoint is gone — prune it so we stop trying.
            subscription.delete()
            logger.info("Pruned dead push subscription id=%s (status=%s)", subscription.id, status)
        else:
            logger.warning("Web push failed for subscription id=%s: %s", subscription.id, exc)
        return False
    except Exception:  # pragma: no cover - network/crypto edge cases must not crash callers
        logger.warning("Unexpected web push error for subscription id=%s", subscription.id, exc_info=True)
        return False


def send_push_to_user(*, user, title, body, url="/", tag=""):
    """Fan a push payload out to all of a user's subscriptions. Returns count sent."""
    if not is_enabled() or user is None:
        return 0

    from accounts.models import NotificationPreference, PushSubscription

    pref = NotificationPreference.objects.filter(user=user).first()
    if pref is not None and not pref.notify_push:
        return 0

    payload = {"title": title, "body": body, "url": url, "tag": tag or "predictstamp"}
    sent = 0
    for subscription in PushSubscription.objects.filter(user=user):
        if _send_one(subscription, payload):
            sent += 1
    return sent


def _type_preference_enabled(notification):
    """Per-type preference gate (independent of the email channel toggle)."""
    from accounts.email_services import _NOTIFICATION_TYPE_TO_PREF

    prefs = getattr(notification.recipient, "notification_preferences", None)
    if prefs is None:
        return True
    pref_attr = _NOTIFICATION_TYPE_TO_PREF.get(notification.notification_type)
    if pref_attr is None:
        return True
    return getattr(prefs, pref_attr, True)


def send_push_for_notification(notification_id):
    """Build and deliver a push for a stored Notification. Safe to call from a task."""
    if not is_enabled():
        return 0

    from accounts.models import Notification

    notification = (
        Notification.objects.select_related("recipient", "actor")
        .filter(id=notification_id)
        .first()
    )
    if notification is None:
        return 0

    # Reuse the per-type preference map used by email so channels stay consistent.
    if not _type_preference_enabled(notification):
        return 0

    actor_name = getattr(notification.actor, "public_name", "") or ""
    title = _push_title(notification, actor_name)
    body = _push_body(notification, actor_name)
    url = _absolute_url(notification.action_url)
    return send_push_to_user(
        user=notification.recipient,
        title=title,
        body=body,
        url=url,
        tag=f"notif-{notification.notification_type}",
    )


def _absolute_url(path):
    base = getattr(settings, "SITE_BASE_URL", "").rstrip("/")
    if path and path.startswith("http"):
        return path
    return f"{base}{path}" if base else (path or "/")


def _push_title(notification, actor_name):
    from accounts.email_services import _notification_subject

    try:
        return _notification_subject(notification, actor_name)
    except Exception:  # pragma: no cover
        return "PredictStamp"


def _push_body(notification, actor_name):
    return notification.action_label or "Open PredictStamp"
