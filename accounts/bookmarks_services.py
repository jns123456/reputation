"""Assemble bookmarked forecasts and forum posts for the Saved page."""

from django.db.models import Count

from accounts.models import Bookmark
from comments.selectors import get_user_prediction_votes
from predictions.models import Prediction
from predictions.selectors import annotate_prediction_interactions
from pulse.models import Post
from pulse.selectors import (
    _get_repost_counts,
    _get_user_reposted_original_ids,
    build_feed_item,
    get_user_pulse_post_votes,
)
from reputation.services import calculate_reputation_stakes


def build_bookmarks_page_items(*, user, target_type=None, limit=100):
    bookmarks_qs = Bookmark.objects.filter(user=user).order_by("-created_at")
    if target_type:
        bookmarks_qs = bookmarks_qs.filter(target_type=target_type)
    bookmarks = list(bookmarks_qs[:limit])
    if not bookmarks:
        return []

    prediction_ids = [
        bookmark.target_id
        for bookmark in bookmarks
        if bookmark.target_type == Bookmark.TargetType.PREDICTION
    ]
    post_ids = [
        bookmark.target_id
        for bookmark in bookmarks
        if bookmark.target_type == Bookmark.TargetType.PULSE_POST
    ]

    predictions_by_id = {
        prediction.id: prediction
        for prediction in annotate_prediction_interactions(
            Prediction.objects.filter(id__in=prediction_ids)
            .exclude(status=Prediction.Status.VOID)
            .select_related("user", "user__profile", "market")
        )
    }
    posts_by_id = {
        post.id: post
        for post in Post.objects.filter(id__in=post_ids)
        .select_related(
            "user",
            "user__profile",
            "reposted_from",
            "reposted_from__user",
            "reposted_from__user__profile",
        )
        .annotate(comment_count=Count("comments", distinct=True))
    }

    prediction_votes = get_user_prediction_votes(user, list(predictions_by_id.keys()))
    post_votes = get_user_pulse_post_votes(user, list(posts_by_id.keys()))
    original_post_ids = list({post.original_post.id for post in posts_by_id.values()})
    repost_counts = _get_repost_counts(original_post_ids)
    user_reposted_ids = _get_user_reposted_original_ids(user, original_post_ids)

    items = []
    for bookmark in bookmarks:
        if bookmark.target_type == Bookmark.TargetType.PREDICTION:
            prediction = predictions_by_id.get(bookmark.target_id)
            if prediction is None:
                continue
            items.append(
                {
                    "bookmark": bookmark,
                    "kind": "prediction",
                    "prediction": prediction,
                    "market": prediction.market,
                    "comment_count": prediction.comment_count,
                    "prediction_vote": prediction_votes.get(prediction.id, 0),
                    "is_bookmarked": True,
                    "reputation_stakes": calculate_reputation_stakes(
                        predicted_outcome=prediction.predicted_outcome,
                        probability_snapshot=prediction.probability_at_prediction_time,
                    ),
                }
            )
            continue

        post = posts_by_id.get(bookmark.target_id)
        if post is None:
            continue
        feed_item = build_feed_item(
            post=post,
            user=user,
            post_votes=post_votes,
            bookmarked_ids={post.id},
            repost_counts=repost_counts,
            user_reposted_ids=user_reposted_ids,
        )
        feed_item["bookmark"] = bookmark
        feed_item["kind"] = "forum_post"
        items.append(feed_item)

    return items
