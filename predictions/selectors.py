from django.db.models import Count, IntegerField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce

from comments.models import Vote
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

def get_market_predictions(market, limit=50):
    qs = (
        Prediction.objects.filter(
            market=market,
            status__in=[Prediction.Status.PENDING, Prediction.Status.RESOLVED],
        )
        .exclude(status=Prediction.Status.VOID)
        .select_related("user", "user__profile")
        .order_by(*DISPLAY_RANK_ORM_FIELDS)
    )
    return annotate_prediction_interactions(qs)[:limit]


def get_prediction_with_interactions(pk):
    return annotate_prediction_interactions(
        Prediction.objects.filter(pk=pk).select_related("user", "user__profile")
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


def get_forecasts_feed(*, market_slug=None, limit=50):
    qs = (
        Prediction.objects.filter(
            status__in=[Prediction.Status.PENDING, Prediction.Status.RESOLVED],
        )
        .exclude(status=Prediction.Status.VOID)
        .select_related("user", "user__profile", "market")
        .order_by("-created_at")
    )
    if market_slug:
        qs = qs.filter(market__slug=market_slug)
    return annotate_prediction_interactions(qs)[:limit]


def get_forecasts_market_options():
    market_ids = (
        Prediction.objects.exclude(status=Prediction.Status.VOID)
        .values_list("market_id", flat=True)
        .distinct()
    )
    return Market.objects.filter(id__in=market_ids).order_by("title")
