from predictions.models import Prediction
from predictions.selectors import (
    annotate_prediction_interactions,
    prefetch_verified_prediction_attestations,
)


def get_user_prediction_history(user, limit=50):
    qs = (
        Prediction.objects.filter(user=user)
        .exclude(status=Prediction.Status.VOID)
        .select_related("market", "user")
        .order_by("-created_at")
    )
    return annotate_prediction_interactions(prefetch_verified_prediction_attestations(qs))[:limit]


def get_top_predictors(limit=20, *, mode=None):
    from accounts.models import UserProfile
    from reputation.ranking_modes import ABSOLUTE, normalize_reputation_ranking_mode

    ranking_mode = normalize_reputation_ranking_mode(mode)
    if ranking_mode == ABSOLUTE:
        ordering = ("-reputation_points", "-reputation_score", "-scored_forecast_count")
    else:
        ordering = ("-reputation_score", "-reputation_points", "-scored_forecast_count")
    return UserProfile.objects.select_related("user").order_by(*ordering)[:limit]


def get_top_popular_users(limit=20):
    from accounts.models import UserProfile

    return UserProfile.objects.select_related("user").order_by(
        "-popularity_score", "-popularity_points"
    )[:limit]


from accounts.user_search_selectors import UserSearchResults, search_user_matches, search_users
