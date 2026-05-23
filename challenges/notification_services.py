"""Challenge-related in-app notifications."""

from accounts.models import Notification, NotificationPreference
from accounts.notification_services import _should_notify_in_app, get_or_create_notification_preferences
from challenges.models import Challenge, ChallengeParticipant


def _challenge_participants(challenge):
    return challenge.participants.filter(
        status=ChallengeParticipant.Status.ACCEPTED,
    ).select_related("user")


def notify_challenge_invitations(*, challenge):
    """Notify invited users about a new challenge."""
    invitations = challenge.participants.filter(
        status=ChallengeParticipant.Status.INVITED,
    ).select_related("user")
    created = []
    for participation in invitations:
        recipient = participation.user
        preferences = get_or_create_notification_preferences(recipient)
        if not preferences.notify_challenge_updates:
            continue
        if not _should_notify_in_app(user_id=recipient.id):
            continue
        notification, was_created = Notification.objects.get_or_create(
            recipient=recipient,
            notification_type=Notification.NotificationType.CHALLENGE_INVITATION,
            challenge=challenge,
            defaults={"actor": challenge.creator},
        )
        if was_created:
            created.append(notification)
    return created


def notify_challenge_market_resolved(*, challenge, market):
    """Notify participants when a challenge event is resolved (no vote details)."""
    if challenge.status != Challenge.Status.ACTIVE:
        return []

    created = []
    for participation in _challenge_participants(challenge):
        recipient = participation.user
        preferences = get_or_create_notification_preferences(recipient)
        if not preferences.notify_challenge_updates:
            continue
        if not _should_notify_in_app(user_id=recipient.id):
            continue

        notification, was_created = Notification.objects.get_or_create(
            recipient=recipient,
            notification_type=Notification.NotificationType.CHALLENGE_MARKET_RESOLVED,
            challenge=challenge,
            market=market,
            defaults={"actor": recipient},
        )
        if was_created:
            created.append(notification)
    return created


def notify_challenge_completed(*, challenge):
    """Notify participants when a challenge finishes."""
    created = []
    for participation in _challenge_participants(challenge):
        recipient = participation.user
        preferences = get_or_create_notification_preferences(recipient)
        if not preferences.notify_challenge_updates:
            continue
        if not _should_notify_in_app(user_id=recipient.id):
            continue

        notification, was_created = Notification.objects.get_or_create(
            recipient=recipient,
            notification_type=Notification.NotificationType.CHALLENGE_COMPLETED,
            challenge=challenge,
            defaults={"actor": recipient},
        )
        if was_created:
            created.append(notification)
    return created


def notify_challenge_accepted(*, challenge, accepter):
    """Notify the challenge creator when an opponent accepts."""
    creator = challenge.creator
    if creator.id == accepter.id:
        return None

    preferences = get_or_create_notification_preferences(creator)
    if not preferences.notify_challenge_updates:
        return None
    if not _should_notify_in_app(user_id=creator.id):
        return None

    notification, _ = Notification.objects.get_or_create(
        recipient=creator,
        notification_type=Notification.NotificationType.CHALLENGE_ACCEPTED,
        challenge=challenge,
        actor=accepter,
    )
    return notification
