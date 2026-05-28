"""Challenge read queries."""

from django.db.models import Q, Sum

from challenges.models import Challenge, ChallengeParticipant
from markets.models import Market
from reputation.models import ReputationEvent

REALIZED_REPUTATION_EVENT_TYPES = [
    ReputationEvent.EventType.CORRECT_PREDICTION,
    ReputationEvent.EventType.INCORRECT_PREDICTION,
    ReputationEvent.EventType.EXITED_PREDICTION,
]


def get_participant_challenge_reputation(*, challenge, user, market_ids=None):
    """Total realized reputation from challenge markets (resolved + exited)."""
    return get_participant_challenge_realized_points(
        challenge=challenge,
        user=user,
        market_ids=market_ids,
    )


def get_participant_challenge_realized_points(*, challenge, user, market_ids=None):
    """Sum of realized reputation events on the given challenge markets."""
    if not challenge.started_at:
        return 0

    if market_ids is None:
        market_ids = challenge.challenge_markets.values_list("market_id", flat=True)
    else:
        market_ids = list(market_ids)

    if not market_ids:
        return 0

    return (
        ReputationEvent.objects.filter(
            user=user,
            prediction__market_id__in=market_ids,
            event_type__in=REALIZED_REPUTATION_EVENT_TYPES,
        ).aggregate(total=Sum("points_delta"))["total"]
        or 0
    )


def get_participant_challenge_unrealized_points(*, challenge, user, open_market_ids=None):
    """Estimated reputation P&L on open challenge markets (same logic as open forecasts).

    Includes pending forecasts placed before the challenge started — the user's
    existing position on a challenge event counts immediately once the challenge is live.
    """
    if not challenge.started_at:
        return 0

    from predictions.models import Prediction
    from reputation.services import calculate_exit_reputation_delta

    if open_market_ids is None:
        open_market_ids = [
            market.id
            for market in get_challenge_markets(challenge)
            if market.status == Market.Status.OPEN
        ]
    else:
        open_market_ids = list(open_market_ids)

    if not open_market_ids:
        return 0

    total = 0
    predictions = Prediction.objects.filter(
        user=user,
        market_id__in=open_market_ids,
        status=Prediction.Status.PENDING,
    ).select_related("market")

    for prediction in predictions:
        total += calculate_exit_reputation_delta(
            predicted_outcome=prediction.predicted_outcome,
            entry_probability_snapshot=prediction.probability_at_prediction_time,
            exit_probability_snapshot=prediction.market.current_probability or {},
            predicted_direction=prediction.predicted_direction,
        )
    return total


def _build_standing_row(*, participant, realized_points, unrealized_points):
    total_points = realized_points + unrealized_points
    return {
        "participant": participant,
        "realized_points": realized_points,
        "unrealized_points": unrealized_points,
        "total_points": total_points,
        "reputation_points": total_points,
        "rank": None,
    }


def _rank_standings(standings, *, score_key="total_points"):
    standings.sort(key=lambda row: row[score_key], reverse=True)
    if not standings:
        return standings

    current_rank = 1
    prev_points = None
    for index, row in enumerate(standings):
        if prev_points is not None and row[score_key] < prev_points:
            current_rank = index + 1
        row["rank"] = current_rank
        prev_points = row[score_key]
    return standings


def get_challenge_standings_for_markets(*, challenge, market_ids):
    """Leaderboard snapshot using only realized reputation on the given markets."""
    participants = challenge.participants.filter(
        status=ChallengeParticipant.Status.ACCEPTED,
    ).select_related("user", "user__profile")

    if not challenge.started_at:
        return [
            _build_standing_row(
                participant=participant,
                realized_points=0,
                unrealized_points=0,
            )
            for participant in participants
        ]

    market_ids = list(market_ids)
    standings = []
    for participant in participants:
        realized = get_participant_challenge_realized_points(
            challenge=challenge,
            user=participant.user,
            market_ids=market_ids,
        )
        standings.append(
            _build_standing_row(
                participant=participant,
                realized_points=realized,
                unrealized_points=0,
            )
        )
    return _rank_standings(standings, score_key="realized_points")


def get_cumulative_resolved_market_ids(*, challenge, through_market):
    """Market IDs resolved in this challenge up to and including through_market."""
    resolved_markets = [
        market
        for market in get_challenge_markets(challenge)
        if market.status == Market.Status.RESOLVED
    ]
    resolved_markets.sort(key=lambda market: (market.resolution_date or market.updated_at, market.pk))

    cumulative_ids = []
    for market in resolved_markets:
        cumulative_ids.append(market.id)
        if market.id == through_market.id:
            return cumulative_ids

    if through_market.status == Market.Status.RESOLVED and through_market.id not in cumulative_ids:
        cumulative_ids.append(through_market.id)
    return cumulative_ids


def get_challenge_standings_snapshot_for_market(*, challenge, market):
    market_ids = get_cumulative_resolved_market_ids(
        challenge=challenge,
        through_market=market,
    )
    return get_challenge_standings_for_markets(challenge=challenge, market_ids=market_ids)


def get_challenge_resolution_snapshots(challenge):
    """Per-event resolution feed with cumulative standings (no vote details)."""
    snapshots = []
    resolved_markets = [
        market
        for market in get_challenge_markets(challenge)
        if market.status == Market.Status.RESOLVED
    ]
    resolved_markets.sort(key=lambda market: (market.resolution_date or market.updated_at, market.pk))

    cumulative_ids = []
    for market in resolved_markets:
        cumulative_ids.append(market.id)
        snapshots.append(
            {
                "market": market,
                "outcome": market.resolved_outcome,
                "resolved_at": market.resolution_date,
                "standings": get_challenge_standings_for_markets(
                    challenge=challenge,
                    market_ids=cumulative_ids,
                ),
            }
        )
    return snapshots


def get_challenge_standings(challenge):
    """Live challenge leaderboard with realized and unrealized reputation columns."""
    participants = challenge.participants.filter(
        status=ChallengeParticipant.Status.ACCEPTED,
    ).select_related("user", "user__profile")

    if not challenge.started_at:
        return [
            _build_standing_row(
                participant=participant,
                realized_points=0,
                unrealized_points=0,
            )
            for participant in participants
        ]

    markets = get_challenge_markets(challenge)
    all_market_ids = [market.id for market in markets]
    open_market_ids = [
        market.id for market in markets if market.status == Market.Status.OPEN
    ]

    standings = []
    for participant in participants:
        realized = get_participant_challenge_realized_points(
            challenge=challenge,
            user=participant.user,
            market_ids=all_market_ids,
        )
        unrealized = get_participant_challenge_unrealized_points(
            challenge=challenge,
            user=participant.user,
            open_market_ids=open_market_ids,
        )
        standings.append(
            _build_standing_row(
                participant=participant,
                realized_points=realized,
                unrealized_points=unrealized,
            )
        )
    return _rank_standings(standings)


def get_challenge_leaderboard(challenge):
    """Leaderboard rows for challenge detail UI (includes invited players before start)."""
    if not challenge.started_at:
        participants = challenge.participants.select_related(
            "user",
            "user__profile",
        ).order_by("created_at")
        return [
            _build_standing_row(
                participant=participant,
                realized_points=0,
                unrealized_points=0,
            )
            for participant in participants
        ]
    return get_challenge_standings(challenge)


def get_active_challenge_contexts_for_market(*, user, market):
    """Pending/active challenges the user is in that include this market."""
    if not user or not user.is_authenticated:
        return []

    return list(
        Challenge.objects.filter(
            Q(participants__user=user)
            & ~Q(participants__status=ChallengeParticipant.Status.DECLINED),
            status__in=[Challenge.Status.PENDING, Challenge.Status.ACTIVE],
            challenge_markets__market=market,
        )
        .distinct()
        .order_by("-created_at")
    )


def get_user_challenges(user):
    """Challenges the user created or participates in."""
    if not user or not user.is_authenticated:
        return Challenge.objects.none()

    return (
        Challenge.objects.filter(
            Q(creator=user)
            | Q(participants__user=user),
        )
        .distinct()
        .select_related("creator", "winner")
        .prefetch_related("challenge_markets__market", "participants__user")
    )


def get_challenge_for_user(*, challenge_id, user):
    return (
        Challenge.objects.filter(
            Q(creator=user) | Q(participants__user=user),
            pk=challenge_id,
        )
        .select_related("creator", "winner")
        .prefetch_related("challenge_markets__market", "participants__user__profile")
        .first()
    )


def get_user_participation(*, challenge, user):
    return ChallengeParticipant.objects.filter(challenge=challenge, user=user).first()


def get_pending_challenge_invitations(user):
    if not user or not user.is_authenticated:
        return ChallengeParticipant.objects.none()

    return (
        ChallengeParticipant.objects.filter(
            user=user,
            status=ChallengeParticipant.Status.INVITED,
            challenge__status=Challenge.Status.PENDING,
        )
        .select_related("challenge", "challenge__creator")
        .prefetch_related("challenge__challenge_markets")
        .order_by("-created_at")
    )


def get_pending_challenge_invitations_count(user):
    if not user or not user.is_authenticated:
        return 0
    return ChallengeParticipant.objects.filter(
        user=user,
        status=ChallengeParticipant.Status.INVITED,
        challenge__status=Challenge.Status.PENDING,
    ).count()


def user_can_view_challenge(*, challenge, user):
    if not user or not user.is_authenticated:
        return False
    if challenge.creator_id == user.id:
        return True
    return challenge.participants.filter(user=user).exists()


def search_open_markets_for_challenge(*, query="", limit=50, selected_ids=None):
    """Open markets for challenge picker, optionally filtered by search text."""
    from markets.selectors import get_markets_list

    qs = get_markets_list(status=Market.Status.OPEN, search=query or None).order_by("title")

    selected_ids = {int(pk) for pk in (selected_ids or []) if str(pk).isdigit()}
    if selected_ids:
        selected_qs = Market.objects.filter(
            id__in=selected_ids,
            status=Market.Status.OPEN,
        )
        qs = (selected_qs | qs).distinct().order_by("title")

    return qs[:limit]


def get_challenge_markets(challenge):
    return [
        entry.market
        for entry in challenge.challenge_markets.select_related("market").order_by(
            "position",
            "id",
        )
    ]


def get_challenge_event_progress(challenge):
    markets = get_challenge_markets(challenge)
    total = len(markets)
    resolved = sum(1 for market in markets if market.status == Market.Status.RESOLVED)
    return {
        "total": total,
        "resolved": resolved,
        "open": total - resolved,
    }


def get_challenge_resolution_activity(challenge):
    """Deprecated alias — use get_challenge_resolution_snapshots."""
    return get_challenge_resolution_snapshots(challenge)
