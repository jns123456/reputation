from predictions.models import Prediction


def get_user_prediction_history(user, limit=50):
    return (
        Prediction.objects.filter(user=user)
        .exclude(status=Prediction.Status.VOID)
        .select_related("market")
        .order_by("-created_at")[:limit]
    )


def get_top_predictors(limit=20):
    from accounts.models import UserProfile

    return UserProfile.objects.select_related("user").order_by(
        "-reputation_score", "-reputation_points"
    )[:limit]


def get_top_popular_users(limit=20):
    from accounts.models import UserProfile

    return UserProfile.objects.select_related("user").order_by(
        "-popularity_score", "-popularity_points"
    )[:limit]
