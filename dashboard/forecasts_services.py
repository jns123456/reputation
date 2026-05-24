"""Assemble Forecasts feed items for templates."""

from accounts.bookmark_selectors import get_user_bookmarked_ids
from accounts.models import Bookmark
from comments.selectors import get_user_prediction_votes
from predictions.selectors import get_forecasts_feed
from reputation.services import calculate_reputation_stakes


def build_forecasts_feed(*, user, market_slug=None, limit=50):
    predictions = list(get_forecasts_feed(market_slug=market_slug, limit=limit))
    prediction_ids = [prediction.id for prediction in predictions]
    prediction_votes = get_user_prediction_votes(user, prediction_ids)
    bookmarked_ids = get_user_bookmarked_ids(
        user,
        Bookmark.TargetType.PREDICTION,
        prediction_ids,
    )

    return [
        {
            "prediction": prediction,
            "market": prediction.market,
            "comment_count": prediction.comment_count,
            "prediction_vote": prediction_votes.get(prediction.id, 0),
            "is_bookmarked": prediction.id in bookmarked_ids,
            "reputation_stakes": calculate_reputation_stakes(
                predicted_outcome=prediction.predicted_outcome,
                probability_snapshot=prediction.probability_at_prediction_time,
            ),
        }
        for prediction in predictions
    ]
