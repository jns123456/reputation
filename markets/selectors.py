from django.db.models import Q

from markets.categories import (
    CANONICAL_CATEGORIES,
    OTHER_CATEGORY,
    get_category_for_slug,
    resolve_market_category_slug,
)
from markets.models import Market


def _market_volume(market) -> float:
    for payload in (market.polymarket_raw or {}, market.polymarket_event_raw or {}):
        for key in ("volumeNum", "volume", "volume24hr"):
            value = payload.get(key)
            if value is None or value == "":
                continue
            try:
                return float(value)
            except (TypeError, ValueError):
                continue
    return 0.0


def get_open_markets_by_canonical_category(*, category_slug, limit=None):
    """Return open markets for a canonical browse category, sorted by volume."""
    category = get_category_for_slug(category_slug)
    if category is None:
        return []

    markets = list(Market.objects.filter(status=Market.Status.OPEN))
    matched = [
        market
        for market in markets
        if resolve_market_category_slug(market) == category.slug
    ]
    matched.sort(key=lambda market: (_market_volume(market), market.updated_at), reverse=True)

    if limit is not None:
        return matched[:limit]
    return matched


def get_category_summaries(*, include_empty=False):
    """
    Summaries for landing category cards: slug, name, description, count, styling.
    """
    counts = {category.slug: 0 for category in CANONICAL_CATEGORIES}
    counts[OTHER_CATEGORY.slug] = 0

    for market in Market.objects.filter(status=Market.Status.OPEN).iterator():
        counts[resolve_market_category_slug(market)] += 1

    summaries = []
    for category in CANONICAL_CATEGORIES:
        count = counts[category.slug]
        if count or include_empty:
            summaries.append({"category": category, "count": count})

    other_count = counts[OTHER_CATEGORY.slug]
    if other_count or include_empty:
        summaries.append({"category": OTHER_CATEGORY, "count": other_count})

    summaries.sort(key=lambda item: item["count"], reverse=True)
    return summaries


def get_markets_list(*, status=None, category=None, search=None):
    qs = Market.objects.all()
    if status:
        qs = qs.filter(status=status)
    if category:
        qs = qs.filter(category__iexact=category)
    if search:
        qs = qs.filter(
            Q(title__icontains=search)
            | Q(description__icontains=search)
            | Q(category__icontains=search)
        )
    return qs


def get_market_categories():
    return (
        Market.objects.exclude(category="")
        .values_list("category", flat=True)
        .distinct()
        .order_by("category")
    )
