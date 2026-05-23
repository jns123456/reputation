from collections import defaultdict

from comments.models import Comment, Vote
from reputation.display_ranking import DISPLAY_RANK_ORM_FIELDS, display_rank_key_for_content


def _sort_comment_tree(nodes):
    nodes.sort(key=display_rank_key_for_content)
    for node in nodes:
        _sort_comment_tree(node.thread_replies)


def attach_comment_votes(threads, vote_map):
    def walk(nodes):
        for node in nodes:
            node.user_vote = vote_map.get(node.id, 0)
            walk(getattr(node, "thread_replies", []))

    walk(threads)


def build_comment_forest(comments):
    """Attach thread_replies to each comment and return top-level nodes."""
    nodes = list(comments)
    for node in nodes:
        node.thread_replies = []

    by_id = {node.id: node for node in nodes}
    top_level = []

    for node in nodes:
        parent_id = node.parent_comment_id
        if parent_id and parent_id in by_id:
            by_id[parent_id].thread_replies.append(node)
        elif not parent_id:
            top_level.append(node)

    _sort_comment_tree(top_level)
    return top_level


def get_prediction_comment_threads(prediction):
    comments = (
        Comment.objects.filter(prediction=prediction)
        .select_related("user", "user__profile")
        .order_by("created_at")
    )
    return build_comment_forest(comments)


def get_market_prediction_discussions(*, market, predictions):
    """Map prediction.id -> list of top-level threaded comments."""
    prediction_ids = [prediction.id for prediction in predictions]
    if not prediction_ids:
        return {}

    comments = (
        Comment.objects.filter(market=market, prediction_id__in=prediction_ids)
        .select_related("user", "user__profile")
        .order_by("created_at")
    )
    grouped = defaultdict(list)
    for comment in comments:
        grouped[comment.prediction_id].append(comment)

    return {
        prediction_id: build_comment_forest(grouped[prediction_id])
        for prediction_id in prediction_ids
    }


def get_market_comments(market):
    """Top-level market comments without a linked prediction (legacy/general)."""
    top_level = (
        Comment.objects.filter(market=market, prediction__isnull=True, parent_comment__isnull=True)
        .select_related("user", "user__profile")
        .prefetch_related("replies__user")
        .order_by(*DISPLAY_RANK_ORM_FIELDS)
    )
    return top_level


def collect_comment_ids(comments):
    ids = []

    def walk(nodes):
        for node in nodes:
            ids.append(node.id)
            walk(node.thread_replies)

    walk(comments)
    return ids


def get_user_comment_votes(user, comment_ids):
    if not user.is_authenticated or not comment_ids:
        return {}

    votes = Vote.objects.filter(
        user=user,
        target_type=Vote.TargetType.COMMENT,
        target_id__in=comment_ids,
    )
    return {vote.target_id: vote.value for vote in votes}


def get_user_prediction_votes(user, prediction_ids):
    if not user.is_authenticated or not prediction_ids:
        return {}

    votes = Vote.objects.filter(
        user=user,
        target_type=Vote.TargetType.PREDICTION,
        target_id__in=prediction_ids,
    )
    return {vote.target_id: vote.value for vote in votes}
