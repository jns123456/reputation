"""Assemble Forecasts feed items for templates."""

from accounts.bookmark_selectors import get_user_bookmarked_ids
from accounts.follow_selectors import get_following_ids
from accounts.models import Bookmark
from comments.models import Vote
from comments.selectors import (
    attach_comment_votes,
    attach_vote_summaries_to_comments,
    collect_comment_ids,
    get_predictions_discussions,
    get_user_comment_votes,
    get_user_prediction_votes,
    get_vote_previews_for_targets,
    get_vote_summaries_for_targets,
)
from predictions.selectors import get_forecasts_feed
from predictions.services import build_forecast_card_metrics
from reputation.services import calculate_reputation_stakes

FORECASTS_FEED_PAGE_SIZE = 20
VALID_FORECAST_SORTS = ("for_you", "recent", "hot", "following")


def build_forecasts_feed(*, user, market_slug=None, sort="recent", page=1, page_size=FORECASTS_FEED_PAGE_SIZE):
    """Return ``(items, has_more)`` for the requested feed page.

    ``hot`` and ``for_you`` are single bounded snapshots (never has_more).
    ``following`` and ``for_you`` are only meaningful for an authenticated
    user; anonymous users fall back to empty / hot respectively.
    """
    if sort not in VALID_FORECAST_SORTS:
        sort = "recent"
    if sort == "following" and not (user and user.is_authenticated):
        return [], False
    if sort == "for_you" and not (user and user.is_authenticated):
        sort = "hot"

    page = max(1, page)
    following_ids = None
    if sort == "following":
        following_ids = list(get_following_ids(user))
        if not following_ids:
            return [], False

    if sort in ("hot", "for_you"):
        predictions = list(
            get_forecasts_feed(
                market_slug=market_slug,
                limit=page_size,
                sort=sort,
                user=user,
            )
        )
        has_more = False
    else:
        offset = (page - 1) * page_size
        fetched = list(
            get_forecasts_feed(
                market_slug=market_slug,
                limit=page_size + 1,
                offset=offset,
                sort=sort,
                following_ids=following_ids,
            )
        )
        has_more = len(fetched) > page_size
        predictions = fetched[:page_size]

    return _build_items(user=user, predictions=predictions), has_more


def _build_items(*, user, predictions):
    from accounts.achievement_services import prefetch_founding_forecaster_flags

    prefetch_founding_forecaster_flags([prediction.user for prediction in predictions])
    prediction_ids = [prediction.id for prediction in predictions]
    prediction_votes = get_user_prediction_votes(user, prediction_ids)
    vote_previews = get_vote_previews_for_targets(
        target_type=Vote.TargetType.PREDICTION,
        target_ids=prediction_ids,
    )
    bookmarked_ids = get_user_bookmarked_ids(
        user,
        Bookmark.TargetType.PREDICTION,
        prediction_ids,
    )

    discussions = get_predictions_discussions(prediction_ids)
    all_comment_ids = []
    for threads in discussions.values():
        all_comment_ids.extend(collect_comment_ids(threads))
    comment_votes = get_user_comment_votes(user, all_comment_ids)
    comment_vote_summaries = get_vote_summaries_for_targets(
        target_type=Vote.TargetType.COMMENT,
        target_ids=all_comment_ids,
    )
    for threads in discussions.values():
        attach_comment_votes(threads, comment_votes)
        attach_vote_summaries_to_comments(threads, comment_vote_summaries)

    return [
        {
            "prediction": prediction,
            "market": prediction.market,
            "threads": discussions.get(prediction.id, []),
            "comment_count": prediction.comment_count,
            "prediction_vote": prediction_votes.get(prediction.id, 0),
            "is_bookmarked": prediction.id in bookmarked_ids,
            "like_preview": vote_previews.get(prediction.id, {}).get("likes", []),
            "dislike_preview": vote_previews.get(prediction.id, {}).get("dislikes", []),
            "reputation_stakes": calculate_reputation_stakes(
                predicted_outcome=prediction.predicted_outcome,
                probability_snapshot=prediction.probability_at_prediction_time,
                predicted_direction=prediction.predicted_direction,
            ),
            "metrics": build_forecast_card_metrics(prediction),
        }
        for prediction in predictions
    ]
