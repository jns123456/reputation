"""Public share context for head-to-head challenge cards."""

from __future__ import annotations

from django.utils.translation import gettext as _

from challenges.models import Challenge, ChallengeParticipant


def get_duel_participants(challenge: Challenge) -> tuple | None:
    """Return (creator, opponent) for a 1v1 challenge when both accepted or invited."""
    accepted = [
        p
        for p in challenge.participants.all()
        if p.status in (
            ChallengeParticipant.Status.ACCEPTED,
            ChallengeParticipant.Status.INVITED,
        )
    ]
    if len(accepted) != 2:
        return None
    creator_part = next((p for p in accepted if p.user_id == challenge.creator_id), None)
    opponent_part = next((p for p in accepted if p.user_id != challenge.creator_id), None)
    if not creator_part or not opponent_part:
        return None
    return creator_part.user, opponent_part.user


def build_challenge_stamp_context(*, challenge: Challenge, markets) -> dict:
    """Share-card fields for public challenge pages."""
    duel = get_duel_participants(challenge)
    primary_market = markets[0] if markets else None
    countdown = None
    if primary_market:
        countdown = primary_market.expiration_countdown

    creator_pick = opponent_pick = None
    if duel and primary_market:
        from predictions.models import Prediction

        creator, opponent = duel
        for user, key in ((creator, "creator_pick"), (opponent, "opponent_pick")):
            forecast = (
                Prediction.objects.filter(
                    user=user,
                    market=primary_market,
                    status__in=[
                        Prediction.Status.PENDING,
                        Prediction.Status.RESOLVED,
                        Prediction.Status.EXITED,
                    ],
                )
                .order_by("-created_at")
                .first()
            )
            if forecast:
                direction = (
                    _("NO")
                    if forecast.predicted_direction == forecast.Direction.NO
                    else _("YES")
                )
                if key == "creator_pick":
                    creator_pick = direction
                else:
                    opponent_pick = direction

    return {
        "duel_users": duel,
        "primary_market": primary_market,
        "countdown": countdown,
        "creator_pick": creator_pick,
        "opponent_pick": opponent_pick,
        "is_duel": duel is not None,
    }


def get_challenge_share_copy(challenge: Challenge) -> dict[str, str]:
    title = challenge.display_title
    if challenge.status == Challenge.Status.COMPLETED and challenge.winner:
        return {
            "title": _("%(winner)s won · %(title)s")
            % {"winner": challenge.winner.public_name, "title": title},
            "text": _("See the head-to-head challenge result on PredictStamp."),
            "sheet_title": _("Share challenge result"),
            "button_label": _("Share challenge"),
        }
    return {
        "title": _("Challenge · %(title)s") % {"title": title},
        "text": _("Head-to-head prediction challenge on PredictStamp."),
        "sheet_title": _("Share challenge"),
        "button_label": _("Share challenge"),
    }
