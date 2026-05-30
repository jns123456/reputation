from django.db.models import Count, IntegerField, OuterRef, Prefetch, Subquery, Value
from django.db.models.functions import Coalesce

from comments.models import Vote
from integrations.models import OffchainAttestation
from markets.models import Market
from predictions.models import Prediction
from reputation.display_ranking import DISPLAY_RANK_ORM_FIELDS


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
):
    """Forecasts feed supporting recent / hot / following sorts.

    ``recent`` and ``following`` paginate by offset/limit; ``hot`` returns a
    bounded, time-decayed snapshot (not paginated). Always returns a list.
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

    return list(qs.order_by("-created_at")[offset : offset + limit])


def get_forecasts_market_options():
    market_ids = (
        Prediction.objects.exclude(status=Prediction.Status.VOID)
        .values_list("market_id", flat=True)
        .distinct()
    )
    return Market.objects.filter(id__in=market_ids).order_by("title")
