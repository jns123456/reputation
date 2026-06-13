"""Outbound engagement email — transactional alerts, daily digest, streak reminders.

These are the platform's only *external* re-engagement triggers (no push yet).
All sending is gated by ``settings.ENGAGEMENT_EMAILS_ENABLED`` and per-user
``NotificationPreference`` so users keep full control (AGENTS.md §10).

Logic here is synchronous and unit-testable; Celery tasks in ``accounts.tasks``
are thin wrappers around these functions.
"""

import logging

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils import translation
from django.utils.encoding import force_str
from django.utils.translation import gettext as _

logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    """Outbound email could not be delivered (Resend/SMTP)."""

    def __init__(self, message, *, provider=""):
        super().__init__(message)
        self.provider = provider


# Maps a notification type to the NotificationPreference flag that controls it.
_NOTIFICATION_TYPE_TO_PREF = {
    "followed_user_prediction": "notify_followed_predictions",
    "new_follower": "notify_new_follower",
    "upvote_received": "notify_votes_received",
    "downvote_received": "notify_votes_received",
    "prediction_resolved": "notify_prediction_resolved",
    "challenge_invitation": "notify_challenge_updates",
    "challenge_market_resolved": "notify_challenge_updates",
    "challenge_completed": "notify_challenge_updates",
    "challenge_accepted": "notify_challenge_updates",
    "comment_reply": "notify_replies",
    "mention": "notify_mentions",
    "market_resolving": "notify_market_resolving",
}

# Challenge alerts are emailed when notify_challenge_updates is on, even if the
# global notify_email toggle is off (invitations are time-sensitive).
_CHALLENGE_EMAIL_NOTIFICATION_TYPES = frozenset(
    key
    for key, pref in _NOTIFICATION_TYPE_TO_PREF.items()
    if pref == "notify_challenge_updates"
)


def _emails_enabled():
    if not getattr(settings, "ENGAGEMENT_EMAILS_ENABLED", True):
        return False
    return _email_delivery_configured()


def _email_delivery_configured():
    """True when we can actually deliver (SMTP, Mailgun add-on, or Resend API)."""
    if getattr(settings, "RESEND_API_KEY", ""):
        return True
    if getattr(settings, "EMAIL_HOST", ""):
        return True
    if getattr(settings, "MAILGUN_SMTP_SERVER", ""):
        return True
    # Dev: console backend works without SMTP.
    if settings.DEBUG:
        return True
    return False


def absolute_url(path):
    base = getattr(settings, "SITE_BASE_URL", "http://localhost:8000").rstrip("/")
    if not path:
        return base
    if path.startswith("http://") or path.startswith("https://"):
        return path
    return f"{base}/{path.lstrip('/')}"


def _email_language(context, language=None):
    return (
        language
        or context.get("language")
        or translation.get_language()
        or settings.LANGUAGE_CODE
    )


def _send(*, subject, recipient_email, template_base, context, language=None):
    """Render a text (+ optional html) template pair and send one message."""
    lang = _email_language(context, language)
    with translation.override(lang):
        raw_subject = subject() if callable(subject) else subject
        resolved_subject = str(raw_subject)
        render_context = {
            **context,
            "subject": resolved_subject,
            "LANGUAGE_CODE": lang,
            "site_url": absolute_url(""),
            "logo_url": absolute_url("/static/images/favicon.svg"),
        }
        text_body = render_to_string(f"emails/{template_base}.txt", render_context)
        html_body = ""
        try:
            html_body = render_to_string(f"emails/{template_base}.html", render_context)
        except Exception:  # html variant is optional
            pass

    resend_key = getattr(settings, "RESEND_API_KEY", "")
    if resend_key:
        return _send_via_resend(
            api_key=resend_key,
            subject=resolved_subject,
            recipient_email=recipient_email,
            text_body=text_body,
            html_body=html_body,
        )

    from django.core.mail import EmailMultiAlternatives

    message = EmailMultiAlternatives(
        subject=resolved_subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient_email],
    )
    if html_body:
        message.attach_alternative(html_body, "text/html")
    return message.send(fail_silently=False)


def _send_via_resend(*, api_key, subject, recipient_email, text_body, html_body):
    """Send via Resend HTTP API (https://resend.com — free tier, one env var)."""
    import requests

    from_email = getattr(
        settings,
        "RESEND_FROM_EMAIL",
        getattr(settings, "DEFAULT_FROM_EMAIL", "PredictStamp <onboarding@resend.dev>"),
    )
    payload = {
        "from": from_email,
        "to": [recipient_email],
        "subject": force_str(subject),
        "text": text_body,
    }
    if html_body:
        payload["html"] = html_body

    response = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=15,
    )
    if response.status_code >= 400:
        detail = response.text[:500]
        logger.warning("Resend API error %s: %s", response.status_code, detail)
        raise EmailDeliveryError(
            _(
                "Email provider rejected the message. "
                "With onboarding@resend.dev you can only send to your Resend account email "
                "until you verify a domain."
            ),
            provider="resend",
        )
    return 1


def _user_wants_email_for(notification):
    user = notification.recipient
    if not user.email:
        return False
    prefs = getattr(user, "notification_preferences", None)
    if prefs is None:
        return False

    pref_attr = _NOTIFICATION_TYPE_TO_PREF.get(notification.notification_type)
    is_challenge_email = (
        notification.notification_type in _CHALLENGE_EMAIL_NOTIFICATION_TYPES
    )

    if is_challenge_email:
        if pref_attr and not getattr(prefs, pref_attr, True):
            return False
        return True

    if not prefs.notify_email:
        return False
    if pref_attr is None:
        return True
    return getattr(prefs, pref_attr, True)


def send_notification_email(notification_id):
    """Send a single transactional email for an in-app notification."""
    if not _emails_enabled():
        return False

    from accounts.models import Notification

    notification = (
        Notification.objects.filter(pk=notification_id)
        .select_related(
            "recipient",
            "recipient__notification_preferences",
            "actor",
            "challenge",
            "challenge__winner",
            "market",
        )
        .first()
    )
    if notification is None:
        return False
    if not _user_wants_email_for(notification):
        return False

    actor_name = notification.actor.public_name if notification.actor_id else "PredictStamp"
    action_url = absolute_url(notification.action_url)
    settings_url = absolute_url("/accounts/settings/alerts/")
    is_challenge_email = (
        notification.notification_type in _CHALLENGE_EMAIL_NOTIFICATION_TYPES
        and notification.challenge_id
    )

    if is_challenge_email:
        from challenges.email_services import build_challenge_notification_email_context

        context = {
            **build_challenge_notification_email_context(
                notification=notification,
                action_url=action_url,
            ),
            "recipient": notification.recipient,
            "settings_url": settings_url,
        }
        template_base = "challenge_notification"
    else:
        context = {
            "notification": notification,
            "recipient": notification.recipient,
            "actor_name": actor_name,
            "action_url": action_url,
            "settings_url": settings_url,
        }
        template_base = "notification"

    sent = _send(
        subject=lambda: _notification_subject(notification, actor_name),
        recipient_email=notification.recipient.email,
        template_base=template_base,
        context=context,
    )
    return bool(sent)


def _notification_subject(notification, actor_name):
    Type = notification.NotificationType
    mapping = {
        Type.FOLLOWED_USER_PREDICTION: _("%(actor)s published a new forecast"),
        Type.NEW_FOLLOWER: _("%(actor)s started following you"),
        Type.UPVOTE_RECEIVED: _("%(actor)s upvoted your content"),
        Type.DOWNVOTE_RECEIVED: _("Your content received a vote"),
        Type.PREDICTION_RESOLVED: _("Your forecast resolved — see your reputation"),
        Type.CHALLENGE_INVITATION: _("%(actor)s invited you to a challenge"),
        Type.CHALLENGE_MARKET_RESOLVED: _("A challenge event just resolved"),
        Type.CHALLENGE_COMPLETED: _("A challenge you joined is complete"),
        Type.CHALLENGE_ACCEPTED: _("%(actor)s accepted your challenge"),
        Type.COMMENT_REPLY: _("%(actor)s replied to your comment"),
        Type.MENTION: _("%(actor)s mentioned you"),
        Type.MARKET_RESOLVING: _("A market you forecast is closing soon"),
    }
    template = mapping.get(notification.notification_type, _("You have a new notification"))
    return template % {"actor": actor_name}


def send_daily_digest(user_id):
    """Send a once-a-day summary of activity to re-engage a user (digest-style)."""
    if not getattr(settings, "DIGEST_EMAILS_ENABLED", False):
        return False
    if not _emails_enabled():
        return False

    from datetime import timedelta

    from accounts.models import Notification, User
    from accounts.streak_services import get_streak

    user = (
        User.objects.filter(pk=user_id)
        .select_related("notification_preferences", "profile")
        .first()
    )
    if user is None or not user.email:
        return False
    prefs = getattr(user, "notification_preferences", None)
    if prefs is None or not prefs.notify_email:
        return False

    since = timezone.now() - timedelta(hours=24)
    recent = list(
        Notification.objects.filter(recipient=user, created_at__gte=since)
        .select_related("actor")
        .order_by("-created_at")[:10]
    )
    unread_count = Notification.objects.filter(recipient=user, read_at__isnull=True).count()

    open_forecasts = 0
    try:
        from predictions.models import Prediction

        open_forecasts = Prediction.objects.filter(
            user=user, status=Prediction.Status.PENDING
        ).count()
    except Exception:  # pragma: no cover - predictions app should always be present
        pass

    streak = get_streak(user)

    # Nothing worth interrupting someone's inbox over.
    if not recent and unread_count == 0 and not streak.is_at_risk():
        return False

    context = {
        "recipient": user,
        "recent_notifications": recent,
        "unread_count": unread_count,
        "open_forecasts": open_forecasts,
        "streak": streak,
        "streak_days": streak.display_streak(),
        "streak_at_risk": streak.is_at_risk(),
        "forecasts_url": absolute_url("/forecasts/"),
        "notifications_url": absolute_url("/accounts/notifications/"),
        "settings_url": absolute_url("/accounts/settings/alerts/"),
    }
    sent = _send(
        subject=lambda: _("Your PredictStamp digest"),
        recipient_email=user.email,
        template_base="daily_digest",
        context=context,
    )
    return bool(sent)


def send_streak_risk_reminder(streak):
    """Warn a user that their active streak ends tonight unless they act."""
    if not getattr(settings, "STREAK_REMINDER_EMAILS_ENABLED", False):
        return False
    if not _emails_enabled():
        return False

    user = streak.user
    if not user.email:
        return False
    prefs = getattr(user, "notification_preferences", None)
    if prefs is None or not prefs.notify_email:
        return False

    context = {
        "recipient": user,
        "streak_days": streak.current_streak,
        "markets_url": absolute_url("/markets/"),
        "settings_url": absolute_url("/accounts/settings/alerts/"),
    }
    sent = _send(
        subject=lambda: _("Your %(days)s-day streak ends tonight")
        % {"days": streak.current_streak},
        recipient_email=user.email,
        template_base="streak_risk",
        context=context,
    )
    return bool(sent)


def send_welcome_email(*, user) -> bool:
    """Send the one-time welcome email after a user joins PredictStamp."""
    if not user.email:
        return False

    context = {
        "recipient": user,
        "home_url": absolute_url("/markets/"),
    }
    sent = _send(
        subject=lambda: _("Welcome to PredictStamp"),
        recipient_email=user.email,
        template_base="welcome",
        context=context,
    )
    return bool(sent)
