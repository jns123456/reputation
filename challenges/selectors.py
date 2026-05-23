"""Challenge read queries."""

from django.db.models import Q, Sum

from challenges.models import Challenge, ChallengeParticipant
from markets.models import Market
from reputation.models import ReputationEvent


def get_participant_challenge_reputation(*, challenge, user, market_ids=None):
    """Total reputation from challenge markets, including pre-existing forecasts."""
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
            event_type__in=[
                ReputationEvent.EventType.CORRECT_PREDICTION,
                ReputationEvent.EventType.INCORRECT_PREDICTION,
            ],
        ).aggregate(total=Sum("points_delta"))["total"]
        or 0
    )


def _rank_standings(standings):
    standings.sort(key=lambda row: row["reputation_points"], reverse=True)
    if not standings:
        return standings

    current_rank = 1
    prev_points = None
    for index, row in enumerate(standings):
        if prev_points is not None and row["reputation_points"] < prev_points:
            current_rank = index + 1
        row["rank"] = current_rank
        prev_points = row["reputation_points"]
    return standings


def get_challenge_standings_for_markets(*, challenge, market_ids):
    """Leaderboard using only reputation earned on the given challenge markets."""
    participants = challenge.participants.filter(
        status=ChallengeParticipant.Status.ACCEPTED,
    ).select_related("user", "user__profile")

    if not challenge.started_at:
        return [
            {"participant": participant, "reputation_points": 0, "rank": None}
            for participant in participants
        ]

    market_ids = list(market_ids)
    standings = []
    for participant in participants:
        total = get_participant_challenge_reputation(
            challenge=challenge,
            user=participant.user,
            market_ids=market_ids,
        )
        standings.append(
            {
                "participant": participant,
                "reputation_points": total,
                "rank": None,
            }
        )
    return _rank_standings(standings)


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
    """Current challenge leaderboard across all resolved events so far."""
    resolved_market_ids = [
        market.id
        for market in get_challenge_markets(challenge)
        if market.status == Market.Status.RESOLVED
    ]
    return get_challenge_standings_for_markets(
        challenge=challenge,
        market_ids=resolved_market_ids,
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
    return get_pending_challenge_invitations(user).count()


def user_can_view_challenge(*, challenge, user):
    if not user or not user.is_authenticated:
        return False
    if challenge.creator_id == user.id:
        return True
    return challenge.participants.filter(user=user).exists()


def search_open_markets_for_challenge(*, query="", limit=50, selected_ids=None):
    """Open markets for challenge picker, optionally filtered by search text."""
    from markets.models import Market
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
