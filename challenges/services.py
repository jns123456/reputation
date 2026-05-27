"""Challenge business logic."""

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from django.db import transaction
from django.utils import timezone

from accounts.follow_selectors import are_mutual_followers
from challenges.models import (
    MAX_CHALLENGE_MARKETS,
    Challenge,
    ChallengeMarket,
    ChallengeParticipant,
)
from challenges.selectors import get_challenge_standings
from markets.models import Market


def create_challenge(*, creator, title="", market_ids, opponent_ids):
    """Create a challenge with up to 10 markets and mutual-follow opponents."""
    if not market_ids:
        raise ValidationError(_("Select at least one event."))
    if len(market_ids) > MAX_CHALLENGE_MARKETS:
        raise ValidationError(
            _("A challenge can include at most %(max)s events.")
            % {"max": MAX_CHALLENGE_MARKETS}
        )
    if len(set(market_ids)) != len(market_ids):
        raise ValidationError(_("Duplicate events are not allowed."))
    if not opponent_ids:
        raise ValidationError(_("Select at least one user to challenge."))
    if creator.id in opponent_ids:
        raise ValidationError(_("You cannot challenge yourself."))

    markets = list(Market.objects.filter(id__in=market_ids))
    if len(markets) != len(market_ids):
        raise ValidationError(_("One or more selected events were not found."))

    from django.contrib.auth import get_user_model

    User = get_user_model()
    opponents = list(User.objects.filter(id__in=opponent_ids))
    if len(opponents) != len(opponent_ids):
        raise ValidationError(_("One or more selected users were not found."))

    for opponent in opponents:
        if not are_mutual_followers(creator, opponent):
            raise ValidationError(
                _("You and @%(username)s must follow each other to challenge them.")
                % {"username": opponent.username}
            )

    with transaction.atomic():
        challenge = Challenge.objects.create(
            creator=creator,
            title=title.strip(),
            status=Challenge.Status.PENDING,
        )

        for position, market in enumerate(markets):
            ChallengeMarket.objects.create(
                challenge=challenge,
                market=market,
                position=position,
            )

        ChallengeParticipant.objects.create(
            challenge=challenge,
            user=creator,
            status=ChallengeParticipant.Status.ACCEPTED,
            joined_at=timezone.now(),
        )

        for opponent in opponents:
            ChallengeParticipant.objects.create(
                challenge=challenge,
                user=opponent,
                status=ChallengeParticipant.Status.INVITED,
            )

    from challenges.notification_services import notify_challenge_invitations

    notify_challenge_invitations(challenge=challenge)
    return challenge


def accept_challenge(*, challenge, user):
    participant = ChallengeParticipant.objects.filter(
        challenge=challenge,
        user=user,
    ).first()
    if not participant:
        raise ValidationError(_("You are not part of this challenge."))
    if participant.status == ChallengeParticipant.Status.DECLINED:
        raise ValidationError(_("You already declined this challenge."))
    if participant.status == ChallengeParticipant.Status.ACCEPTED:
        return participant

    participant.status = ChallengeParticipant.Status.ACCEPTED
    participant.joined_at = timezone.now()
    participant.save(update_fields=["status", "joined_at"])

    _mark_challenge_invitation_read(challenge=challenge, user=user)

    from challenges.notification_services import notify_challenge_accepted

    notify_challenge_accepted(challenge=challenge, accepter=user)
    _maybe_activate_challenge(challenge)
    return participant


def decline_challenge(*, challenge, user):
    participant = ChallengeParticipant.objects.filter(
        challenge=challenge,
        user=user,
    ).first()
    if not participant:
        raise ValidationError(_("You are not part of this challenge."))
    if participant.challenge.creator_id == user.id:
        raise ValidationError(_("The creator cannot decline their own challenge."))

    participant.status = ChallengeParticipant.Status.DECLINED
    participant.save(update_fields=["status"])

    _mark_challenge_invitation_read(challenge=challenge, user=user)
    if not challenge.participants.filter(
        status=ChallengeParticipant.Status.INVITED,
    ).exists():
        _maybe_activate_challenge(challenge)
    return participant


def cancel_challenge(*, challenge, user):
    if challenge.creator_id != user.id:
        raise ValidationError(_("Only the creator can cancel a challenge."))
    if challenge.status != Challenge.Status.PENDING:
        raise ValidationError(_("Only pending challenges can be cancelled."))

    challenge.status = Challenge.Status.CANCELLED
    challenge.save(update_fields=["status", "updated_at"])
    return challenge


def _mark_challenge_invitation_read(*, challenge, user):
    from accounts.models import Notification

    Notification.objects.filter(
        recipient=user,
        challenge=challenge,
        notification_type=Notification.NotificationType.CHALLENGE_INVITATION,
        read_at__isnull=True,
    ).update(read_at=timezone.now())


def _maybe_activate_challenge(challenge):
    if challenge.status != Challenge.Status.PENDING:
        return challenge

    has_pending_invites = challenge.participants.filter(
        status=ChallengeParticipant.Status.INVITED,
    ).exists()
    if has_pending_invites:
        return challenge

    accepted_opponents = challenge.participants.filter(
        status=ChallengeParticipant.Status.ACCEPTED,
    ).exclude(user_id=challenge.creator_id).exists()
    if not accepted_opponents:
        return challenge

    challenge.status = Challenge.Status.ACTIVE
    challenge.started_at = timezone.now()
    challenge.save(update_fields=["status", "started_at", "updated_at"])
    return challenge


def check_challenge_completion(*, market):
    """Finalize active challenges when all their markets have resolved."""
    from challenges.notification_services import notify_challenge_market_resolved

    challenge_markets = ChallengeMarket.objects.filter(
        market=market,
        challenge__status=Challenge.Status.ACTIVE,
    ).select_related("challenge")

    for entry in challenge_markets:
        challenge = entry.challenge
        if market.status == Market.Status.RESOLVED:
            notify_challenge_market_resolved(challenge=challenge, market=market)

        market_ids = challenge.challenge_markets.values_list("market_id", flat=True)
        unresolved = Market.objects.filter(
            id__in=market_ids,
        ).exclude(status=Market.Status.RESOLVED).exists()
        if unresolved:
            continue
        _complete_challenge(challenge)


def _complete_challenge(challenge):
    if challenge.status != Challenge.Status.ACTIVE:
        return challenge

    standings = get_challenge_standings(challenge)
    if not standings:
        challenge.status = Challenge.Status.COMPLETED
        challenge.completed_at = timezone.now()
        challenge.save(update_fields=["status", "completed_at", "updated_at"])
        return challenge

    top_score = standings[0]["reputation_points"]
    leaders = [row for row in standings if row["reputation_points"] == top_score]
    winner = leaders[0]["participant"].user if len(leaders) == 1 else None

    challenge.status = Challenge.Status.COMPLETED
    challenge.completed_at = timezone.now()
    challenge.winner = winner
    challenge.save(update_fields=["status", "completed_at", "winner", "updated_at"])

    from challenges.notification_services import notify_challenge_completed

    notify_challenge_completed(challenge=challenge)
    return challenge
