from django.db.models import Q

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


def search_users(*, query="", limit=20):
    """Find active users by username, display name, or bio."""
    from accounts.models import User

    cleaned = (query or "").strip()
    if len(cleaned) < 2:
        return User.objects.none()

    return (
        User.objects.filter(is_active=True)
        .select_related("profile")
        .filter(
            Q(username__icontains=cleaned)
            | Q(display_name__icontains=cleaned)
            | Q(bio__icontains=cleaned)
        )
        .order_by("-profile__reputation_score", "-profile__popularity_score")[:limit]
    )
