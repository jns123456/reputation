"""Selectors for per-category reputation and popularity."""

from accounts.models import UserCategoryStats
from markets.categories import get_all_chart_categories, get_category_for_slug


def get_user_category_breakdown(user):
    """Return stats for every chart category, including zeros."""
    stats_by_slug = {
        row.category_slug: row
        for row in UserCategoryStats.objects.filter(user=user)
    }
    breakdown = []
    for category in get_all_chart_categories():
        stat = stats_by_slug.get(category.slug)
        breakdown.append(
            {
                "category": category,
                "reputation_points": stat.reputation_points if stat else 0,
                "popularity_points": stat.popularity_points if stat else 0,
                "prediction_count": stat.prediction_count if stat else 0,
                "correct_prediction_count": stat.correct_prediction_count if stat else 0,
                "incorrect_prediction_count": stat.incorrect_prediction_count if stat else 0,
            }
        )
    return breakdown


def get_top_predictors_by_category(category_slug, limit=50, *, mode=None):
    from reputation.ranking_modes import ABSOLUTE, normalize_reputation_ranking_mode

    ranking_mode = normalize_reputation_ranking_mode(mode)
    if ranking_mode == ABSOLUTE:
        ordering = ("-reputation_points", "-reputation_score", "-scored_forecast_count")
    else:
        ordering = ("-reputation_score", "-reputation_points", "-scored_forecast_count")
    return (
        UserCategoryStats.objects.filter(category_slug=category_slug)
        .select_related("user", "user__profile")
        .order_by(*ordering)[:limit]
    )


def get_top_popular_users_by_category(category_slug, limit=50):
    return (
        UserCategoryStats.objects.filter(category_slug=category_slug)
        .select_related("user", "user__profile")
        .order_by("-popularity_score", "-popularity_points")[:limit]
    )


def get_user_category_rank(user, category_slug, *, ranking="reputation", mode=None):
    """Return 1-based rank in a category, or None if user has no stats row."""
    from reputation.ranking_modes import ABSOLUTE, normalize_reputation_ranking_mode

    stats = UserCategoryStats.objects.filter(user=user, category_slug=category_slug).first()
    if stats is None:
        return None

    if ranking == "popularity":
        higher = UserCategoryStats.objects.filter(
            category_slug=category_slug,
        ).filter(
            popularity_score__gt=stats.popularity_score,
        ).count()
        tied = UserCategoryStats.objects.filter(
            category_slug=category_slug,
            popularity_score=stats.popularity_score,
            popularity_points__gt=stats.popularity_points,
        ).count()
    elif normalize_reputation_ranking_mode(mode) == ABSOLUTE:
        higher = UserCategoryStats.objects.filter(
            category_slug=category_slug,
            reputation_points__gt=stats.reputation_points,
        ).count()
        tied = UserCategoryStats.objects.filter(
            category_slug=category_slug,
            reputation_points=stats.reputation_points,
            reputation_score__gt=stats.reputation_score,
        ).count()
    else:
        higher = UserCategoryStats.objects.filter(
            category_slug=category_slug,
        ).filter(
            reputation_score__gt=stats.reputation_score,
        ).count()
        tied = UserCategoryStats.objects.filter(
            category_slug=category_slug,
            reputation_score=stats.reputation_score,
            reputation_points__gt=stats.reputation_points,
        ).count()

    return higher + tied + 1


def validate_category_slug(slug):
    return get_category_for_slug(slug)
