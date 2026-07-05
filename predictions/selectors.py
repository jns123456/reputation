from django.core.cache import cache
from django.db.models import Count, IntegerField, OuterRef, Prefetch, Q, Subquery, Value
from django.db.models.functions import Coalesce

from comments.models import Vote
from integrations.models import OffchainAttestation
from markets.models import Market
from predictions.models import Prediction
from reputation.display_ranking import DISPLAY_RANK_ORM_FIELDS


FORECASTS_MARKET_OPTIONS_CACHE_KEY = "forecasts_market_options_v1"
FORECASTS_MARKET_OPTIONS_CACHE_SECONDS = 120


def _prediction_vote_count_subquery(value):
    return (
        Vote.objects.filter(
            target_type=Vote.TargetType.PREDICTION,
            target_id=OuterRef("pk"),
            value=value,
        )
        .values("target_id")
        .annotate(c=Count("pk"))
        .values("c")
    )


def annotate_prediction_interactions(qs):
    return qs.annotate(
        comment_count=Count("comments", distinct=True),
        like_count=Coalesce(
            Subquery(_prediction_vote_count_subquery(1), output_field=IntegerField()),
            Value(0),
        ),
        dislike_count=Coalesce(
            Subquery(_prediction_vote_count_subquery(-1), output_field=IntegerField()),
            Value(0),
        ),
    )


def prefetch_verified_prediction_attestations(qs):
    return qs.prefetch_related(
        Prefetch(
            "attestations",
            queryset=OffchainAttestation.objects.filter(
                schema__kind="prediction_claim",
                status=OffchainAttestation.Status.VERIFIED,
            ).select_related("schema"),
        )
    )

def get_market_predictions(market, limit=50):
    qs = (
        Prediction.objects.filter(
            market=market,
            status__in=[
                Prediction.Status.PENDING,
                Prediction.Status.RESOLVED,
                Prediction.Status.EXITED,
            ],
        )
        .exclude(status=Prediction.Status.VOID)
        .select_related("user", "user__profile", "market")
        .order_by(*DISPLAY_RANK_ORM_FIELDS)
    )
    return annotate_prediction_interactions(prefetch_verified_prediction_attestations(qs))[:limit]


def get_prediction_with_interactions(pk):
    return annotate_prediction_interactions(
        prefetch_verified_prediction_attestations(
            Prediction.objects.filter(pk=pk).select_related("user", "user__profile", "market")
        )
    ).first()


def get_user_prediction_summary(user):
    """Aggregate non-void forecast counts for profile and dashboard display."""
    aggregated = (
        Prediction.objects.filter(user=user)
        .exclude(status=Prediction.Status.VOID)
        .aggregate(
            total=Count("id"),
            correct=Count(
                "id",
                filter=Q(status=Prediction.Status.RESOLVED, is_correct=True),
            ),
            incorrect=Count(
                "id",
                filter=Q(status=Prediction.Status.RESOLVED, is_correct=False),
            ),
            open=Count("id", filter=Q(status=Prediction.Status.PENDING)),
            exited=Count("id", filter=Q(status=Prediction.Status.EXITED)),
        )
    )
    resolved = aggregated["correct"] + aggregated["incorrect"]
    accuracy_pct = round(aggregated["correct"] * 100 / resolved) if resolved else None
    return {
        **aggregated,
        "resolved": resolved,
        "accuracy_pct": accuracy_pct,
    }


def get_user_active_prediction(user, market):
    return (
        Prediction.objects.filter(
            user=user,
            market=market,
            status=Prediction.Status.PENDING,
        )
        .order_by("-created_at")
        .first()
    )


def attach_user_forecasts_to_markets(user, markets):
    """Annotate each market with ``user_forecast`` (pending prediction or None)."""
    market_list = list(markets)
    if not market_list:
        return market_list

    if not user.is_authenticated:
        for market in market_list:
            market.user_forecast = None
        return market_list

    market_ids = [market.id for market in market_list]
    pending_by_market = {}
    for prediction in (
        Prediction.objects.filter(
            user=user,
            market_id__in=market_ids,
            status=Prediction.Status.PENDING,
        )
        .order_by("market_id", "-created_at")
        .select_related("market")
    ):
        pending_by_market.setdefault(prediction.market_id, prediction)

    for market in market_list:
        market.user_forecast = pending_by_market.get(market.id)

    return market_list


def get_user_closed_prediction_history(user, *, limit=100, status=None):
    """Resolved and early-exited forecasts — the user's public track record."""
    qs = (
        Prediction.objects.filter(
            user=user,
            status__in=[Prediction.Status.RESOLVED, Prediction.Status.EXITED],
        )
        .select_related("market", "user")
        .order_by(Coalesce("resolved_at", "exited_at", "created_at").desc())
    )
    if status == Prediction.Status.RESOLVED:
        qs = qs.filter(status=Prediction.Status.RESOLVED)
    elif status == Prediction.Status.EXITED:
        qs = qs.filter(status=Prediction.Status.EXITED)
    return annotate_prediction_interactions(prefetch_verified_prediction_attestations(qs))[
        :limit
    ]


def get_user_open_predictions(user, limit=100):
    qs = (
        Prediction.objects.filter(
            user=user,
            status=Prediction.Status.PENDING,
            market__status=Market.Status.OPEN,
        )
        .select_related("user", "user__profile", "market")
        .order_by("market__close_date", "-created_at")
    )
    return annotate_prediction_interactions(prefetch_verified_prediction_attestations(qs))[:limit]


HOT_CANDIDATE_POOL = 150


def get_forecasts_feed(
    *,
    market_slug=None,
    limit=50,
    offset=0,
    sort="recent",
    following_ids=None,
    user=None,
):
    """Forecasts feed supporting recent / hot / following / for_you sorts.

    ``recent`` and ``following`` paginate by offset/limit; ``hot`` and
    ``for_you`` return a bounded, time-decayed snapshot (not paginated).
    Always returns a list.
    """
    from dashboard.ranking import hot_score

    qs = (
        Prediction.objects.filter(
            status__in=[
                Prediction.Status.PENDING,
                Prediction.Status.RESOLVED,
                Prediction.Status.EXITED,
            ],
        )
        .exclude(status=Prediction.Status.VOID)
        .select_related("user", "user__profile", "market")
    )
    if market_slug:
        qs = qs.filter(market__slug=market_slug)
    if sort == "following":
        ids = list(following_ids or [])
        if not ids:
            return []
        qs = qs.filter(user_id__in=ids)

    qs = annotate_prediction_interactions(prefetch_verified_prediction_attestations(qs))

    if sort == "hot":
        candidates = list(qs.order_by("-created_at")[:HOT_CANDIDATE_POOL])
        candidates.sort(
            key=lambda p: hot_score(
                points=p.popularity_score,
                created_at=p.created_at,
                engagement=p.comment_count,
            ),
            reverse=True,
        )
        return candidates[:limit]

    if sort == "for_you":
        from dashboard.personalization import personalize_feed

        candidates = list(qs.order_by("-created_at")[:HOT_CANDIDATE_POOL])
        return personalize_feed(
            user=user,
            candidates=candidates,
            limit=limit,
            get_author_id=lambda p: p.user_id,
            get_category_slug=lambda p: p.market.canonical_category_slug,
            get_market_id=lambda p: p.market_id,
            get_points=lambda p: p.popularity_score,
            get_created_at=lambda p: p.created_at,
            get_engagement=lambda p: p.comment_count,
        )

    return list(qs.order_by("-created_at")[offset : offset + limit])


CALIBRATION_BUCKETS = ((0, 20), (20, 40), (40, 60), (60, 80), (80, 100))
CALIBRATION_MAX_SAMPLE = 500


def get_user_calibration(user):
    """Accuracy by entry-probability bucket for resolved forecasts.

    Shows whether a forecaster's hit rate matches the market-implied odds they
    entered at (display-only — never feeds scoring). Returns a list of bucket
    dicts ordered low→high probability.
    """
    from reputation.services import get_predicted_outcome_probability

    predictions = Prediction.objects.filter(
        user=user,
        status=Prediction.Status.RESOLVED,
        is_correct__isnull=False,
    ).order_by("-resolved_at")[:CALIBRATION_MAX_SAMPLE]

    counts = {bucket: [0, 0] for bucket in CALIBRATION_BUCKETS}  # bucket -> [total, correct]
    for prediction in predictions:
        snapshot = prediction.probability_at_prediction_time or {}
        if not snapshot:
            continue
        try:
            entry_percent = (
                get_predicted_outcome_probability(
                    prediction.predicted_outcome,
                    snapshot,
                    predicted_direction=prediction.predicted_direction,
                )
                * 100
            )
        except Exception:
            continue
        for low, high in CALIBRATION_BUCKETS:
            if low <= entry_percent < high or (high == 100 and entry_percent == 100):
                counts[(low, high)][0] += 1
                if prediction.is_correct:
                    counts[(low, high)][1] += 1
                break

    rows = []
    for low, high in CALIBRATION_BUCKETS:
        total, correct = counts[(low, high)]
        rows.append(
            {
                "low": low,
                "high": high,
                "total": total,
                "correct": correct,
                "accuracy_pct": round(correct * 100 / total) if total else None,
                "midpoint": (low + high) // 2,
            }
        )
    return rows


SCORECARD_TOP_PERFORMERS = 5
SCORECARD_HIGHLIGHTS = 3


def get_market_resolution_scorecard(market):
    """Aggregate recap for a resolved market — community accuracy, top performers, highlights.

    Returns ``None`` when the market is not resolved. Uses immutable ``ReputationEvent``
    rows as the source of truth for points on this market.
    """
    from reputation.models import ReputationEvent
    from reputation.services import get_predicted_outcome_probability

    if market.status != Market.Status.RESOLVED:
        return None

    events = list(
        ReputationEvent.objects.filter(prediction__market=market)
        .select_related("user", "user__profile", "prediction", "prediction__market")
        .order_by("-points_delta", "-created_at")
    )

    resolved_qs = Prediction.objects.filter(
        market=market,
        status=Prediction.Status.RESOLVED,
        is_correct__isnull=False,
    )
    correct_count = resolved_qs.filter(is_correct=True).count()
    incorrect_count = resolved_qs.filter(is_correct=False).count()
    resolved_count = correct_count + incorrect_count
    exited_count = Prediction.objects.filter(
        market=market,
        status=Prediction.Status.EXITED,
    ).count()
    scored_count = len(events)

    accuracy_pct = round(correct_count * 100 / resolved_count) if resolved_count else None
    total_reputation_delta = sum(event.points_delta for event in events)

    user_totals = {}
    for event in events:
        user_totals[event.user_id] = user_totals.get(event.user_id, 0) + event.points_delta

    user_by_id = {event.user_id: event.user for event in events}
    top_performers = [
        {
            "rank": index + 1,
            "user": user_by_id[user_id],
            "points_delta": points,
        }
        for index, (user_id, points) in enumerate(
            sorted(user_totals.items(), key=lambda item: item[1], reverse=True)[
                :SCORECARD_TOP_PERFORMERS
            ]
        )
    ]

    positive_events = [event for event in events if event.points_delta > 0]
    negative_events = [event for event in events if event.points_delta < 0]
    biggest_wins = sorted(positive_events, key=lambda event: event.points_delta, reverse=True)[
        :SCORECARD_HIGHLIGHTS
    ]
    biggest_losses = sorted(negative_events, key=lambda event: event.points_delta)[
        :SCORECARD_HIGHLIGHTS
    ]

    contrarian_winners = []
    for prediction in resolved_qs.filter(is_correct=True).select_related(
        "user", "user__profile"
    ):
        snapshot = prediction.probability_at_prediction_time or {}
        if not snapshot:
            continue
        try:
            entry_percent = int(
                round(
                    get_predicted_outcome_probability(
                        prediction.predicted_outcome,
                        snapshot,
                        predicted_direction=prediction.predicted_direction,
                    )
                    * 100
                )
            )
        except Exception:
            continue
        contrarian_winners.append(
            {
                "prediction": prediction,
                "user": prediction.user,
                "entry_prob_percent": entry_percent,
            }
        )
    contrarian_winners.sort(key=lambda row: row["entry_prob_percent"])
    contrarian_winners = contrarian_winners[:SCORECARD_HIGHLIGHTS]

    return {
        "has_scored_forecasts": scored_count > 0,
        "scored_count": scored_count,
        "resolved_count": resolved_count,
        "exited_count": exited_count,
        "correct_count": correct_count,
        "incorrect_count": incorrect_count,
        "accuracy_pct": accuracy_pct,
        "total_reputation_delta": total_reputation_delta,
        "top_performers": top_performers,
        "biggest_wins": biggest_wins,
        "biggest_losses": biggest_losses,
        "contrarian_winners": contrarian_winners,
        "resolved_outcome": market.resolved_outcome or "",
        "resolved_at": market.resolution_date,
    }


def get_forecasts_market_options():
    cached = cache.get(FORECASTS_MARKET_OPTIONS_CACHE_KEY)
    if cached is not None:
        return cached

    market_ids = (
        Prediction.objects.exclude(status=Prediction.Status.VOID)
        .values_list("market_id", flat=True)
        .distinct()
    )
    options = list(Market.objects.filter(id__in=market_ids).order_by("title"))
    cache.set(
        FORECASTS_MARKET_OPTIONS_CACHE_KEY,
        options,
        FORECASTS_MARKET_OPTIONS_CACHE_SECONDS,
    )
    return options


def clear_forecasts_market_options_cache():
    cache.delete(FORECASTS_MARKET_OPTIONS_CACHE_KEY)
