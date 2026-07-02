"""Challenge read queries."""

from django.db.models import Q, Sum

from accounts.models import User
from challenges.models import Challenge, ChallengeGroup, ChallengeParticipant
from markets.models import Market
from reputation.models import ReputationEvent

REALIZED_REPUTATION_EVENT_TYPES = [
    ReputationEvent.EventType.CORRECT_PREDICTION,
    ReputationEvent.EventType.INCORRECT_PREDICTION,
    ReputationEvent.EventType.EXITED_PREDICTION,
]


def get_participant_challenge_reputation(*, challenge, participant, market_ids=None):
    """Total realized reputation from challenge markets (resolved + exited)."""
    return get_participant_challenge_realized_points(
        challenge=challenge,
        participant=participant,
        market_ids=market_ids,
    )


def _challenge_reputation_cutoff(*, challenge, participant):
    """Earliest moment challenge reputation counts for this participant."""
    if not challenge.started_at:
        return None
    joined = participant.joined_at
    if joined is None:
        return challenge.started_at
    return max(joined, challenge.started_at)


def get_participant_challenge_realized_points(*, challenge, participant, market_ids=None):
    """Sum of realized reputation events on challenge markets after the participant joins.

    Only events at or after max(joined_at, challenge.started_at) count — exits or
    resolutions before acceptance do not affect challenge standings.
    """
    if not challenge.started_at:
        return 0

    cutoff = _challenge_reputation_cutoff(challenge=challenge, participant=participant)
    if cutoff is None:
        return 0

    user = participant.user
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
            created_at__gte=cutoff,
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
            participant=participant,
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
            participant=participant,
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
        .select_related("creator", "winner", "challenge_group")
        .prefetch_related("challenge_markets__market", "participants__user__profile")
        .first()
    )


def get_challenge_for_spectator(challenge_id):
    """Read-only fetch for non-participants (public spectating).

    Only started or finished challenges are spectatable — pending invitations
    stay private to the invited users.
    """
    return (
        Challenge.objects.filter(
            pk=challenge_id,
            status__in=[Challenge.Status.ACTIVE, Challenge.Status.COMPLETED],
        )
        .select_related("creator", "winner", "challenge_group")
        .prefetch_related("challenge_markets__market", "participants__user__profile")
        .first()
    )


def get_challenge_participant_by_token(*, challenge_id, invite_token):
    if not invite_token:
        return None
    return (
        ChallengeParticipant.objects.filter(
            challenge_id=challenge_id,
            invite_token=invite_token,
            status=ChallengeParticipant.Status.INVITED,
        )
        .select_related("challenge", "user", "challenge__creator")
        .first()
    )


def get_head_to_head_record(*, user, opponent):
    """Completed 1v1 duel record between two users.

    Returns ``{"wins": int, "losses": int, "ties": int, "total": int}`` from
    ``user``'s perspective. Only counts completed challenges where exactly the
    two users were accepted participants.
    """
    from django.db.models import Count

    duel_ids = (
        ChallengeParticipant.objects.filter(
            status=ChallengeParticipant.Status.ACCEPTED,
            challenge__status=Challenge.Status.COMPLETED,
        )
        .values("challenge_id")
        .annotate(
            accepted_count=Count("id"),
            has_user=Count("id", filter=Q(user=user)),
            has_opponent=Count("id", filter=Q(user=opponent)),
        )
        .filter(accepted_count=2, has_user=1, has_opponent=1)
        .values_list("challenge_id", flat=True)
    )
    duels = Challenge.objects.filter(pk__in=list(duel_ids))
    wins = losses = ties = 0
    for challenge in duels:
        if challenge.winner_id == user.id:
            wins += 1
        elif challenge.winner_id == opponent.id:
            losses += 1
        else:
            ties += 1
    return {"wins": wins, "losses": losses, "ties": ties, "total": wins + losses + ties}


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
    from markets.selectors import (
        forecastable_market_q,
        get_markets_list,
        order_markets_chronologically,
        sort_markets_chronologically,
    )

    qs = order_markets_chronologically(
        get_markets_list(status=Market.Status.OPEN, search=query or None).filter(
            forecastable_market_q()
        )
    )

    selected_ids = {int(pk) for pk in (selected_ids or []) if str(pk).isdigit()}
    markets = list(qs[:limit])
    if selected_ids:
        existing_ids = {market.id for market in markets}
        extra_ids = selected_ids - existing_ids
        if extra_ids:
            extras = list(
                Market.objects.filter(
                    forecastable_market_q(),
                    id__in=extra_ids,
                )
            )
            markets = sort_markets_chronologically(extras + markets)[:limit]
    return markets[:limit]


CHALLENGE_CATEGORY_MARKET_LIMIT = 100


def get_challenge_category_browse_context(*, category_slug, area_slug="", search="", selected_ids=None):
    """Markets and navigation context for challenge event picker category view."""
    from markets.categories import get_category_for_slug
    from markets.selectors import (
        filter_markets_by_browse_area,
        get_browse_area,
        get_browse_area_summaries,
        get_category_display_markets,
        get_open_markets_by_canonical_category,
    )

    category = get_category_for_slug(category_slug)
    if category is None:
        return None

    total_markets = [
        market
        for market in get_open_markets_by_canonical_category(category_slug=category_slug)
        if market.is_forecastable
    ]
    area_summaries = get_browse_area_summaries(category_slug=category_slug, markets=total_markets)
    active_area = get_browse_area(category_slug, area_slug) if area_slug else None

    display_markets = total_markets
    if active_area:
        display_markets = filter_markets_by_browse_area(
            markets=total_markets,
            category_slug=category_slug,
            area_slug=area_slug,
        )

    markets = get_category_display_markets(
        category_slug=category_slug,
        area_slug=area_slug or None,
        search=search or None,
        limit=CHALLENGE_CATEGORY_MARKET_LIMIT,
        markets=total_markets,
    )

    selected_ids_set = {int(pk) for pk in (selected_ids or []) if str(pk).isdigit()}
    if selected_ids_set:
        existing_ids = {market.id for market in markets}
        extra_ids = selected_ids_set - existing_ids
        if extra_ids:
            from markets.selectors import forecastable_market_q, sort_markets_chronologically

            extras = list(
                Market.objects.filter(forecastable_market_q(), id__in=extra_ids)
            )
            markets = sort_markets_chronologically(extras + list(markets))

    return {
        "category": category,
        "area_summaries": area_summaries,
        "active_area": active_area,
        "active_area_slug": area_slug,
        "total_market_count": len(total_markets),
        "market_count": len(display_markets),
        "markets": markets,
        "search_query": search,
    }


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


def get_user_challenge_groups(user):
    if not user or not user.is_authenticated:
        return ChallengeGroup.objects.none()
    return (
        ChallengeGroup.objects.filter(owner=user)
        .prefetch_related("members")
        .order_by("name", "id")
    )


def get_challenge_group_for_user(*, group_id, user):
    if not user or not user.is_authenticated:
        return None
    return (
        ChallengeGroup.objects.filter(pk=group_id, owner=user)
        .prefetch_related("members")
        .first()
    )


def get_challengeable_user_queryset(*, user):
    """Active, non-anonymous platform users the given user can challenge."""
    if not user or not user.is_authenticated:
        return User.objects.none()
    return (
        User.objects.filter(is_active=True)
        .exclude(identity_mode=User.IdentityMode.ANONYMOUS)
        .exclude(pk=user.pk)
        .order_by("username")
    )


def get_challengeable_users(*, user):
    return list(get_challengeable_user_queryset(user=user))


def is_challengeable_user(*, challenger, opponent):
    if not challenger or not opponent:
        return False
    if challenger.pk == opponent.pk:
        return False
    if not opponent.is_active:
        return False
    if opponent.identity_mode == User.IdentityMode.ANONYMOUS:
        return False
    return True
