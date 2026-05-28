"""Forum feed read queries."""

from django.db.models import Count, IntegerField, OuterRef, Prefetch, Subquery, Value
from django.db.models.functions import Coalesce

from accounts.bookmark_selectors import get_user_bookmarked_ids
from accounts.models import Bookmark
from comments.models import Vote
from comments.selectors import build_comment_forest, collect_comment_ids, get_vote_previews_for_targets, get_vote_summaries_for_targets, attach_vote_summaries_to_comments
from pulse.models import Poll, PollOption, PollVote, Post


def _vote_count_subquery(*, target_type, value):
    return (
        Vote.objects.filter(
            target_type=target_type,
            target_id=OuterRef("pk"),
            value=value,
        )
        .values("target_id")
        .annotate(c=Count("pk"))
        .values("c")
    )


def _post_vote_count_subquery(value):
    return _vote_count_subquery(
        target_type=Vote.TargetType.PULSE_POST,
        value=value,
    )


def _pulse_comment_vote_count_subquery(value):
    return _vote_count_subquery(
        target_type=Vote.TargetType.PULSE_COMMENT,
        value=value,
    )


def annotate_post_interactions(qs):
    return qs.annotate(
        like_count=Coalesce(
            Subquery(_post_vote_count_subquery(1), output_field=IntegerField()),
            Value(0),
        ),
        dislike_count=Coalesce(
            Subquery(_post_vote_count_subquery(-1), output_field=IntegerField()),
            Value(0),
        ),
    )


FORUM_FEED_ORDER = ("-created_at",)


def _poll_options_queryset():
    return PollOption.objects.annotate(
        vote_count=Count("votes", distinct=True),
    ).order_by("position", "id")


def _poll_options_prefetch(path="poll"):
    return Prefetch(
        f"{path}__options",
        queryset=_poll_options_queryset(),
    )


def _post_queryset_base():
    return annotate_post_interactions(
        Post.objects.select_related(
            "user",
            "user__profile",
            "reposted_from",
            "reposted_from__user",
            "reposted_from__user__profile",
            "poll",
            "reposted_from__poll",
        ).prefetch_related(
            _poll_options_prefetch("poll"),
            _poll_options_prefetch("reposted_from__poll"),
        )
    )


def get_user_poll_votes(user, poll_ids):
    if not user.is_authenticated or not poll_ids:
        return {}

    votes = PollVote.objects.filter(user=user, poll_id__in=poll_ids).select_related("option")
    return {vote.poll_id: vote.option_id for vote in votes}


def build_poll_context(*, post, user, user_poll_votes=None):
    try:
        poll = post.poll
    except Poll.DoesNotExist:
        return None

    if user_poll_votes is None:
        user_poll_votes = get_user_poll_votes(user, [poll.id])

    options = list(
        _poll_options_queryset().filter(poll=poll),
    )
    total_votes = sum(getattr(option, "vote_count", 0) for option in options)
    user_option_id = user_poll_votes.get(poll.id)
    is_author = user.is_authenticated and user.id == post.user_id
    show_results = poll.is_closed or user_option_id is not None or is_author

    for option in options:
        vote_count = getattr(option, "vote_count", 0)
        option.vote_pct = round(vote_count * 100 / total_votes) if total_votes else 0

    return {
        "poll": poll,
        "poll_options": options,
        "poll_total_votes": total_votes,
        "poll_user_option_id": user_option_id,
        "poll_show_results": show_results,
    }


HOT_CANDIDATE_POOL = 150


def get_pulse_posts(*, limit=50, offset=0, sort="recent", following_ids=None):
    """Forum posts supporting recent / hot / following sorts.

    ``recent`` / ``following`` paginate by offset/limit; ``hot`` is a bounded,
    time-decayed snapshot. Always returns a list.
    """
    from dashboard.ranking import hot_score

    qs = _post_queryset_base().annotate(comment_count=Count("comments", distinct=True))

    if sort == "following":
        ids = list(following_ids or [])
        if not ids:
            return []
        qs = qs.filter(user_id__in=ids)

    if sort == "hot":
        candidates = list(qs.order_by(*FORUM_FEED_ORDER)[:HOT_CANDIDATE_POOL])
        candidates.sort(
            key=lambda p: hot_score(
                points=getattr(p, "popularity_score", 0),
                created_at=p.created_at,
                engagement=p.comment_count,
            ),
            reverse=True,
        )
        return candidates[:limit]

    return list(qs.order_by(*FORUM_FEED_ORDER)[offset : offset + limit])


def get_post_with_interactions(pk):
    return _post_queryset_base().filter(pk=pk).first()


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


def build_feed_item(*, post, user, post_votes, bookmarked_ids, repost_counts, user_reposted_ids, user_poll_votes=None, vote_previews=None):
    original_post = post.original_post
    original_id = original_post.id
    content_post = original_post if post.is_repost else post
    poll_ids = []
    try:
        poll_ids.append(content_post.poll.id)
    except Poll.DoesNotExist:
        pass
    if user_poll_votes is None:
        user_poll_votes = get_user_poll_votes(user, poll_ids)
    poll_context = build_poll_context(
        post=content_post,
        user=user,
        user_poll_votes=user_poll_votes,
    )
    preview = (vote_previews or {}).get(post.id, {})
    item = {
        "post": post,
        "original_post": original_post,
        "comment_count": post.comment_count,
        "post_vote": post_votes.get(post.id, 0),
        "is_bookmarked": post.id in bookmarked_ids,
        "repost_count": repost_counts.get(original_id, 0),
        "is_reposted": original_id in user_reposted_ids,
        "like_preview": preview.get("likes", []),
        "dislike_preview": preview.get("dislikes", []),
    }
    if poll_context:
        item.update(poll_context)
    return item


FORUM_FEED_PAGE_SIZE = 20
VALID_FORUM_SORTS = ("recent", "hot", "following")


def build_pulse_feed(*, user, sort="recent", page=1, page_size=FORUM_FEED_PAGE_SIZE):
    """Return ``(items, has_more)`` for the requested forum feed page."""
    from accounts.follow_selectors import get_following_ids

    if sort not in VALID_FORUM_SORTS:
        sort = "recent"
    if sort == "following" and not (user and user.is_authenticated):
        return [], False

    page = max(1, page)
    following_ids = None
    if sort == "following":
        following_ids = list(get_following_ids(user))
        if not following_ids:
            return [], False

    if sort == "hot":
        posts = list(get_pulse_posts(limit=page_size, sort="hot"))
        has_more = False
    else:
        offset = (page - 1) * page_size
        fetched = list(
            get_pulse_posts(
                limit=page_size + 1,
                offset=offset,
                sort=sort,
                following_ids=following_ids,
            )
        )
        has_more = len(fetched) > page_size
        posts = fetched[:page_size]

    return _build_pulse_items(user=user, posts=posts), has_more


def _build_pulse_items(*, user, posts):
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
    poll_ids = []
    for post in posts:
        content_post = post.original_post if post.is_repost else post
        try:
            poll_ids.append(content_post.poll.id)
        except Poll.DoesNotExist:
            continue
    user_poll_votes = get_user_poll_votes(user, poll_ids)
    vote_previews = get_vote_previews_for_targets(
        target_type=Vote.TargetType.PULSE_POST,
        target_ids=post_ids,
    )

    return [
        build_feed_item(
            post=post,
            user=user,
            post_votes=post_votes,
            bookmarked_ids=bookmarked_ids,
            repost_counts=repost_counts,
            user_reposted_ids=user_reposted_ids,
            user_poll_votes=user_poll_votes,
            vote_previews=vote_previews,
        )
        for post in posts
    ]


def annotate_comment_interactions(qs):
    return qs.annotate(
        like_count=Coalesce(
            Subquery(
                _pulse_comment_vote_count_subquery(1),
                output_field=IntegerField(),
            ),
            Value(0),
        ),
        dislike_count=Coalesce(
            Subquery(
                _pulse_comment_vote_count_subquery(-1),
                output_field=IntegerField(),
            ),
            Value(0),
        ),
        reply_count=Count("replies", distinct=True),
    )


def get_comment_with_interactions(pk):
    from pulse.models import Comment

    return annotate_comment_interactions(
        Comment.objects.select_related("user", "user__profile", "post")
    ).filter(pk=pk).first()


def get_post_comment_threads(post):
    from pulse.models import Comment

    comments = annotate_comment_interactions(
        Comment.objects.filter(post=post).select_related(
            "user",
            "user__profile",
        )
    ).order_by("created_at")
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

    post = get_post_with_interactions(post.pk)
    if post is None:
        return None
    threads = get_post_comment_threads(post)
    comment_ids = collect_comment_ids(threads)
    vote_map = get_user_pulse_comment_votes(user, comment_ids)
    comment_vote_summaries = get_vote_summaries_for_targets(
        target_type=Vote.TargetType.PULSE_COMMENT,
        target_ids=comment_ids,
    )
    post_vote_previews = get_vote_previews_for_targets(
        target_type=Vote.TargetType.PULSE_POST,
        target_ids=[post.id],
    )
    original_post = post.original_post
    repost_counts = _get_repost_counts([original_post.id])
    user_reposted_ids = _get_user_reposted_original_ids(user, [original_post.id])

    def walk(nodes):
        for node in nodes:
            node.user_vote = vote_map.get(node.id, 0)
            walk(getattr(node, "thread_replies", []))

    walk(threads)
    attach_vote_summaries_to_comments(threads, comment_vote_summaries)
    content_post = original_post if post.is_repost else post
    poll_context = build_poll_context(post=content_post, user=user)
    context = {
        "post": post,
        "original_post": original_post,
        "threads": threads,
        "post_vote": get_user_pulse_post_votes(user, [post.id]).get(post.id, 0),
        "is_bookmarked": post.id
        in get_user_bookmarked_ids(user, Bookmark.TargetType.PULSE_POST, [post.id]),
        "comment_count": Comment.objects.filter(post=post).count(),
        "repost_count": repost_counts.get(original_post.id, 0),
        "is_reposted": original_post.id in user_reposted_ids,
        "like_preview": post_vote_previews.get(post.id, {}).get("likes", []),
        "dislike_preview": post_vote_previews.get(post.id, {}).get("dislikes", []),
    }
    if poll_context:
        context.update(poll_context)
    return context
