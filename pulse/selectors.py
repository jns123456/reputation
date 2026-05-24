"""Forum feed read queries."""

from django.db.models import Count

from accounts.bookmark_selectors import get_user_bookmarked_ids
from accounts.models import Bookmark
from comments.models import Vote
from comments.selectors import build_comment_forest, collect_comment_ids
from pulse.models import Post
from reputation.display_ranking import DISPLAY_RANK_ORM_FIELDS


def get_pulse_posts(*, limit=50):
    return (
        Post.objects.select_related(
            "user",
            "user__profile",
            "reposted_from",
            "reposted_from__user",
            "reposted_from__user__profile",
        )
        .annotate(comment_count=Count("comments", distinct=True))
        .order_by(*DISPLAY_RANK_ORM_FIELDS)[:limit]
    )


def get_user_pulse_post_votes(user, post_ids):
    if not user.is_authenticated or not post_ids:
        return {}

    votes = Vote.objects.filter(
        user=user,
        target_type=Vote.TargetType.PULSE_POST,
        target_id__in=post_ids,
    )
    return {vote.target_id: vote.value for vote in votes}


def _get_repost_counts(original_post_ids):
    if not original_post_ids:
        return {}

    rows = (
        Post.objects.filter(reposted_from_id__in=original_post_ids)
        .values("reposted_from")
        .annotate(count=Count("id"))
    )
    return {row["reposted_from"]: row["count"] for row in rows}


def _get_user_reposted_original_ids(user, original_post_ids):
    if not user.is_authenticated or not original_post_ids:
        return set()

    return set(
        Post.objects.filter(
            user=user,
            reposted_from_id__in=original_post_ids,
        ).values_list("reposted_from_id", flat=True)
    )


def build_feed_item(*, post, user, post_votes, bookmarked_ids, repost_counts, user_reposted_ids):
    original_post = post.original_post
    original_id = original_post.id
    return {
        "post": post,
        "original_post": original_post,
        "comment_count": post.comment_count,
        "post_vote": post_votes.get(post.id, 0),
        "is_bookmarked": post.id in bookmarked_ids,
        "repost_count": repost_counts.get(original_id, 0),
        "is_reposted": original_id in user_reposted_ids,
    }


def build_pulse_feed(*, user, limit=50):
    posts = list(get_pulse_posts(limit=limit))
    post_ids = [post.id for post in posts]
    original_post_ids = list({post.original_post.id for post in posts})
    post_votes = get_user_pulse_post_votes(user, post_ids)
    bookmarked_ids = get_user_bookmarked_ids(
        user,
        Bookmark.TargetType.PULSE_POST,
        post_ids,
    )
    repost_counts = _get_repost_counts(original_post_ids)
    user_reposted_ids = _get_user_reposted_original_ids(user, original_post_ids)

    return [
        build_feed_item(
            post=post,
            user=user,
            post_votes=post_votes,
            bookmarked_ids=bookmarked_ids,
            repost_counts=repost_counts,
            user_reposted_ids=user_reposted_ids,
        )
        for post in posts
    ]


def get_post_comment_threads(post):
    from pulse.models import Comment

    comments = (
        Comment.objects.filter(post=post)
        .select_related("user", "user__profile")
        .order_by("created_at")
    )
    return build_comment_forest(comments)


def get_user_pulse_comment_votes(user, comment_ids):
    if not user.is_authenticated or not comment_ids:
        return {}

    votes = Vote.objects.filter(
        user=user,
        target_type=Vote.TargetType.PULSE_COMMENT,
        target_id__in=comment_ids,
    )
    return {vote.target_id: vote.value for vote in votes}


def build_post_discussion(*, user, post):
    from pulse.models import Comment

    post = (
        Post.objects.select_related(
            "user",
            "user__profile",
            "reposted_from",
            "reposted_from__user",
            "reposted_from__user__profile",
        )
        .filter(pk=post.pk)
        .first()
    )
    threads = get_post_comment_threads(post)
    comment_ids = collect_comment_ids(threads)
    vote_map = get_user_pulse_comment_votes(user, comment_ids)
    original_post = post.original_post
    repost_counts = _get_repost_counts([original_post.id])
    user_reposted_ids = _get_user_reposted_original_ids(user, [original_post.id])

    def walk(nodes):
        for node in nodes:
            node.user_vote = vote_map.get(node.id, 0)
            walk(getattr(node, "thread_replies", []))

    walk(threads)
    return {
        "post": post,
        "original_post": original_post,
        "threads": threads,
        "post_vote": get_user_pulse_post_votes(user, [post.id]).get(post.id, 0),
        "is_bookmarked": post.id
        in get_user_bookmarked_ids(user, Bookmark.TargetType.PULSE_POST, [post.id]),
        "comment_count": Comment.objects.filter(post=post).count(),
        "repost_count": repost_counts.get(original_post.id, 0),
        "is_reposted": original_post.id in user_reposted_ids,
    }
