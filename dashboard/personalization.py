"""For You feed personalization — heuristic, popularity-side only (§6).

Re-ranks the same bounded recent candidate pool used by the ``hot`` sort with
per-user signals: category affinity (from the user's own forecasting history
and followed topics), followed authors, and a per-author diversity cap. No ML,
no new request-time heavy queries — affinity is one aggregate, cached.
"""

from django.core.cache import cache
from django.db.models import Count

from dashboard.ranking import hot_score

AFFINITY_CACHE_SECONDS = 60 * 15
# Score boosts expressed in hot_score units (1.0 ≈ 12.5h of recency).
CATEGORY_AFFINITY_MAX_BOOST = 1.0
FOLLOWED_TOPIC_BOOST = 1.0
FOLLOWED_AUTHOR_BOOST = 0.75
WATCHED_MARKET_BOOST = 0.5
# Diversity: one author can hold at most this many slots per page.
MAX_ITEMS_PER_AUTHOR = 2


def _affinity_cache_key(user):
    return f"foryou-affinity:{user.id}"


def get_user_category_affinity(user):
    """Return ``{canonical_category_slug: weight 0..1}`` for the user's history."""
    if not (user and user.is_authenticated):
        return {}

    cached = cache.get(_affinity_cache_key(user))
    if cached is not None:
        return cached

    from predictions.models import Prediction

    rows = (
        Prediction.objects.filter(user=user)
        .exclude(status=Prediction.Status.VOID)
        .exclude(market__canonical_category_slug="")
        .values("market__canonical_category_slug")
        .annotate(n=Count("id"))
        .order_by("-n")[:20]
    )
    top = rows[0]["n"] if rows else 0
    affinity = {
        row["market__canonical_category_slug"]: row["n"] / top for row in rows if top
    }

    from accounts.follow_selectors import get_followed_topic_slugs

    for slug in get_followed_topic_slugs(user):
        affinity[slug] = 1.0

    cache.set(_affinity_cache_key(user), affinity, AFFINITY_CACHE_SECONDS)
    return affinity


def clear_user_affinity_cache(user):
    cache.delete(_affinity_cache_key(user))


def personalize_feed(*, user, candidates, limit, get_author_id, get_category_slug,
                     get_market_id, get_points, get_created_at, get_engagement):
    """Re-rank a bounded candidate pool for the requesting user.

    Accessor callables keep this reusable for predictions and forum posts
    without coupling to either model.
    """
    affinity = get_user_category_affinity(user)

    following_ids = set()
    watched_market_ids = set()
    if user and user.is_authenticated:
        from accounts.follow_selectors import get_following_ids, get_watched_market_ids

        following_ids = set(get_following_ids(user))
        watched_market_ids = set(get_watched_market_ids(user))

    def score(item):
        base = hot_score(
            points=get_points(item),
            created_at=get_created_at(item),
            engagement=get_engagement(item),
        )
        boost = 0.0
        category = get_category_slug(item)
        if category and category in affinity:
            boost += CATEGORY_AFFINITY_MAX_BOOST * affinity[category]
        if get_author_id(item) in following_ids:
            boost += FOLLOWED_AUTHOR_BOOST
        if get_market_id(item) in watched_market_ids:
            boost += WATCHED_MARKET_BOOST
        return base + boost

    ranked = sorted(candidates, key=score, reverse=True)

    selected = []
    per_author = {}
    overflow = []
    for item in ranked:
        author_id = get_author_id(item)
        if per_author.get(author_id, 0) >= MAX_ITEMS_PER_AUTHOR:
            overflow.append(item)
            continue
        per_author[author_id] = per_author.get(author_id, 0) + 1
        selected.append(item)
        if len(selected) >= limit:
            return selected

    # Backfill from capped authors only when the pool is too small otherwise.
    for item in overflow:
        selected.append(item)
        if len(selected) >= limit:
            break
    return selected
