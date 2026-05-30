"""Challenge-specific email context for transactional notifications."""

from django.utils.translation import gettext as _

from accounts.models import Notification
from challenges.selectors import get_challenge_markets


def build_challenge_notification_email_context(*, notification, action_url):
    """Build template context for challenge-related notification emails."""
    challenge = notification.challenge
    markets = get_challenge_markets(challenge) if challenge else []
    actor_name = notification.actor.public_name if notification.actor_id else "PredictStamp"

    intro = _challenge_email_intro(
        notification_type=notification.notification_type,
        actor_name=actor_name,
        challenge=challenge,
        market=notification.market,
    )

    return {
        "notification": notification,
        "challenge": challenge,
        "challenge_markets": markets,
        "highlight_market": notification.market if notification.market_id else None,
        "actor_name": actor_name,
        "action_url": action_url,
        "intro_text": intro,
        "view_label": _("View challenge"),
    }


def _challenge_email_intro(*, notification_type, actor_name, challenge, market):
    challenge_title = challenge.display_title if challenge else ""

    if notification_type == Notification.NotificationType.CHALLENGE_INVITATION:
        return _("%(actor)s invited you to a challenge: %(title)s.") % {
            "actor": actor_name,
            "title": challenge_title,
        }

    if notification_type == Notification.NotificationType.CHALLENGE_ACCEPTED:
        return _("%(actor)s accepted your challenge: %(title)s.") % {
            "actor": actor_name,
            "title": challenge_title,
        }

    if notification_type == Notification.NotificationType.CHALLENGE_MARKET_RESOLVED:
        market_title = market.display_title if market else _("An event")
        return _(
            "An event in your challenge “%(challenge)s” was resolved: %(market)s."
        ) % {
            "challenge": challenge_title,
            "market": market_title,
        }

    if notification_type == Notification.NotificationType.CHALLENGE_COMPLETED:
        winner = challenge.winner if challenge else None
        if winner:
            return _('Your challenge “%(title)s” is complete. Winner: %(winner)s.') % {
                "title": challenge_title,
                "winner": winner.public_name,
            }
        return _('Your challenge “%(title)s” ended in a tie.') % {
            "title": challenge_title,
        }

    return _("You have a new update on a challenge you joined.")
