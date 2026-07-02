"""Display context for public prediction stamp cards (viral share surfaces)."""

from __future__ import annotations

from django.utils import timezone
from django.utils.translation import gettext as _

from accounts.category_selectors import get_user_category_rank
from accounts.models import UserCategoryStats
from predictions.models import Prediction


def _category_top_percent(*, rank: int, total: int) -> int | None:
    if rank is None or total < 2:
        return None
    return max(1, min(99, round(rank / total * 100)))


def get_user_category_top_percent(user, category_slug: str) -> int | None:
    """Return ``Top N%`` slice for a category leaderboard, or None."""
    rank = get_user_category_rank(user, category_slug=category_slug)
    if rank is None:
        return None
    total = UserCategoryStats.objects.filter(category_slug=category_slug).count()
    return _category_top_percent(rank=rank, total=total)


def get_days_before_resolution(prediction: Prediction) -> int | None:
    """Days between forecast creation and market resolution (or resolve time)."""
    end = prediction.market.resolution_date or prediction.resolved_at
    if end is None:
        return None
    if timezone.is_naive(end):
        end = timezone.make_aware(end, timezone.get_current_timezone())
    start = prediction.created_at
    if timezone.is_naive(start):
        start = timezone.make_aware(start, timezone.get_current_timezone())
    days = (end.date() - start.date()).days
    return max(days, 0)


def build_prediction_stamp_context(*, prediction: Prediction, metrics: dict) -> dict:
    """Stamp-card fields for /p/<id>/ and OG rendering."""
    market = prediction.market
    category_slug = getattr(market, "canonical_category_slug", "") or ""
    category_name = ""
    if category_slug:
        from markets.categories import get_category_for_slug

        category = get_category_for_slug(category_slug)
        if category:
            category_name = str(category.name)

    profile = getattr(prediction.user, "profile", None)
    reputation_points = getattr(profile, "reputation_points", 0) if profile else 0
    category_top_percent = None
    if category_slug:
        category_top_percent = get_user_category_top_percent(prediction.user, category_slug)

    direction_label = (
        _("NO") if prediction.predicted_direction == Prediction.Direction.NO else _("YES")
    )
    pick_label = prediction.predicted_outcome
    if prediction.predicted_direction == Prediction.Direction.NO:
        pick_label = f"{_('No')} {pick_label}"

    card_variant = "open"
    if prediction.status == Prediction.Status.RESOLVED:
        card_variant = "called_it" if prediction.is_correct else "aged_badly"

    return {
        "card_variant": card_variant,
        "direction_label": direction_label,
        "pick_label": pick_label,
        "reputation_points": reputation_points,
        "category_slug": category_slug,
        "category_name": category_name,
        "category_top_percent": category_top_percent,
        "days_before_resolution": get_days_before_resolution(prediction)
        if prediction.status == Prediction.Status.RESOLVED
        else None,
        "embed_html": _build_embed_html(prediction_id=prediction.pk),
        "challenge_url": _build_challenge_url(market_id=market.pk),
        "forum_share_url": _build_forum_share_url(prediction_id=prediction.pk),
        "entry_percent": metrics.get("entry_percent"),
        "pnl_delta": metrics.get("pnl_delta"),
    }


def _build_embed_html(*, prediction_id: int) -> str:
    return (
        f'<iframe src="https://predictstamp.com/p/{prediction_id}/embed/" '
        f'width="400" height="520" frameborder="0" '
        f'title="PredictStamp forecast" loading="lazy"></iframe>'
    )


def _build_challenge_url(*, market_id: int) -> str:
    from django.urls import reverse

    return reverse("challenges:create") + f"?market={market_id}"


def _build_forum_share_url(*, prediction_id: int) -> str:
    from django.urls import reverse

    return reverse("forum:feed") + f"?share_prediction={prediction_id}&anonymous=1#forum-compose"
