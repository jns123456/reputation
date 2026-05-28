"""Build Forum page context shared by page and HTMX partial views."""

from pulse.selectors import (
    FORUM_FEED_PAGE_SIZE,
    VALID_FORUM_SORTS,
    build_pulse_feed,
)


def _normalize_sort(sort, *, user):
    sort = (sort or "recent").strip()
    if sort not in VALID_FORUM_SORTS:
        sort = "recent"
    if sort == "following" and not (user and user.is_authenticated):
        sort = "recent"
    return sort


def _parse_page(raw):
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 1


def get_forum_page_context(*, request, sort="recent", page=1):
    sort = _normalize_sort(sort, user=request.user)
    page = _parse_page(page)
    feed_items, has_more = build_pulse_feed(
        user=request.user,
        sort=sort,
        page=page,
    )
    return {
        "feed_items": feed_items,
        "active_sort": sort,
        "feed_page": page,
        "feed_has_more": has_more,
        "feed_next_page": page + 1,
        "feed_page_size": FORUM_FEED_PAGE_SIZE,
    }
