from predictions.models import Prediction


def get_market_predictions(market, limit=50):
    return (
        Prediction.objects.filter(market=market, status__in=[Prediction.Status.PENDING, Prediction.Status.RESOLVED])
        .exclude(status=Prediction.Status.VOID)
        .select_related("user")
        .order_by("-created_at")[:limit]
    )


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
