from collections import defaultdict

from django.conf import settings
from django.db.models import Count, Q

from markets.categories import (
    CANONICAL_CATEGORIES,
    FIFA_WORLD_CUP_CATEGORY_SLUG,
    OTHER_CATEGORY,
    get_category_for_slug,
)
from markets.browse_areas import (
    get_browse_area,
    get_browse_areas_for_category,
    market_matches_browse_area,
)
from markets.models import Market
from markets.sort_options import market_volume, normalize_sort_filter, sort_markets
from markets.source_filters import kalshi_enabled

MARKET_HUB_CATEGORY_SLUG_ORDER = (
    "politics",
    "sports",
    "crypto",
    "economy",
    "science-tech",
    "world",
    "pop-culture",
    "fifa-world-cup-2026",
    "other",
)

SOURCE_DISPLAY_ORDER = (
    Market.Source.POLYMARKET,
    Market.Source.KALSHI,
)
CATEGORY_BROWSE_LIMIT = 48
MARKET_CARD_DEFER_FIELDS = (
    "description",
    "polymarket_raw",
    "polymarket_event_raw",
    "kalshi_raw",
    "kalshi_event_raw",
)


def _market_card_queryset(qs):
    return qs.defer(*MARKET_CARD_DEFER_FIELDS)


def market_card_queryset(qs):
    """Lightweight queryset for market cards (skips large text fields)."""
    return _market_card_queryset(qs)


def _exclude_disabled_sources(markets):
    excluded = {Market.Source.MANUAL}
    if not kalshi_enabled():
        excluded.add(Market.Source.KALSHI)
    if isinstance(markets, list):
        return [market for market in markets if market.source not in excluded]
    return markets.exclude(source__in=excluded)


def _sort_markets_by_volume(markets):
    if isinstance(markets, list):
        return sorted(
            markets,
            key=lambda market: (market_volume(market), market.updated_at),
            reverse=True,
        )
    return markets.order_by("-volume_total", "-updated_at")


def blend_markets_by_source(markets, *, limit=CATEGORY_BROWSE_LIMIT):
    """Interleave markets by source so Kalshi is visible alongside Polymarket."""
    sorted_markets = _sort_markets_by_volume(markets)
    if not sorted_markets:
        return []

    buckets = defaultdict(list)
    for market in sorted_markets:
        buckets[market.source].append(market)

    if len(buckets) <= 1:
        return sorted_markets[:limit]

    source_order = [source for source in SOURCE_DISPLAY_ORDER if source in buckets]
    source_order.extend(source for source in buckets if source not in source_order)

    blended = []
    indices = {source: 0 for source in source_order}
    while len(blended) < limit:
        added = False
        for source in source_order:
            index = indices[source]
            if index < len(buckets[source]):
                blended.append(buckets[source][index])
                indices[source] = index + 1
                added = True
                if len(blended) >= limit:
                    break
        if not added:
            break
    return blended


def filter_markets_by_search(*, markets, search):
    """Filter an in-memory market list by title, description, or category text."""
    query = (search or "").strip()
    if not query:
        return markets
    needle = query.casefold()
    filtered = []
    for market in markets:
        if (
            needle in (market.title or "").casefold()
            or needle in (market.category or "").casefold()
        ):
            filtered.append(market)
            continue
        description = getattr(market, "description", None) or ""
        if needle in description.casefold():
            filtered.append(market)
    return filtered


def get_category_display_markets(
    *,
    category_slug,
    limit=CATEGORY_BROWSE_LIMIT,
    source=None,
    area_slug=None,
    search=None,
    markets=None,
):
    """Markets for category browse cards, balanced across external sources."""
    if markets is None:
        markets = get_open_markets_by_canonical_category(category_slug=category_slug)
    if area_slug:
        markets = filter_markets_by_browse_area(
            markets=markets,
            category_slug=category_slug,
            area_slug=area_slug,
        )
    if search:
        markets = filter_markets_by_search(markets=markets, search=search)
    if source:
        markets = [market for market in markets if market.source == source]
        return _sort_markets_by_volume(markets)[:limit]
    if search:
        return _sort_markets_by_volume(markets)[:limit]
    return blend_markets_by_source(markets, limit=limit)


def get_open_markets_by_canonical_category(*, category_slug, limit=None):
    """Return open markets for a canonical browse category, sorted by volume."""
    category = get_category_for_slug(category_slug)
    if category is None:
        return []

    qs = _exclude_disabled_sources(
        _market_card_queryset(
            Market.objects.filter(
                status=Market.Status.OPEN,
                canonical_category_slug=category.slug,
            )
        )
    )
    qs = qs.order_by("-volume_total", "-updated_at")

    if limit is not None:
        return list(qs[:limit])
    return list(qs)


def get_browse_area_summaries(*, category_slug, markets=None):
    """Count open markets per sub-area; only areas with at least one market."""
    if markets is None:
        markets = get_open_markets_by_canonical_category(category_slug=category_slug)

    summaries = []
    for area in get_browse_areas_for_category(category_slug):
        count = sum(1 for market in markets if market_matches_browse_area(market, area))
        if count:
            summaries.append({"area": area, "count": count})

    summaries.sort(key=lambda item: item["count"], reverse=True)
    return summaries


def filter_markets_by_browse_area(*, markets, category_slug, area_slug):
    area = get_browse_area(category_slug, area_slug)
    if area is None:
        return markets
    return [market for market in markets if market_matches_browse_area(market, area)]


def get_category_summaries(*, include_empty=False):
    """
    Summaries for landing category cards: slug, name, description, count, styling.
    """
    counts = {category.slug: 0 for category in CANONICAL_CATEGORIES}
    counts[OTHER_CATEGORY.slug] = 0

    for row in (
        _exclude_disabled_sources(Market.objects.filter(status=Market.Status.OPEN))
        .values("canonical_category_slug")
        .annotate(count=Count("id"))
    ):
        slug = row["canonical_category_slug"] or OTHER_CATEGORY.slug
        counts[slug] = counts.get(slug, 0) + row["count"]

    summaries = []
    for category in CANONICAL_CATEGORIES:
        count = counts[category.slug]
        if count or include_empty:
            summaries.append({"category": category, "count": count})

    other_count = counts[OTHER_CATEGORY.slug]
    if other_count or include_empty:
        summaries.append({"category": OTHER_CATEGORY, "count": other_count})

    summaries.sort(key=lambda item: item["count"], reverse=True)
    if include_empty:
        return summaries
    return _pin_featured_world_cup_summary(summaries, counts)


def _pin_featured_world_cup_summary(summaries, counts):
    """Always show FIFA World Cup 2026 first on the landing page."""
    world_cup = get_category_for_slug(FIFA_WORLD_CUP_CATEGORY_SLUG)
    if world_cup is None:
        return summaries

    summaries = [item for item in summaries if item["category"].slug != world_cup.slug]
    count = counts.get(world_cup.slug)
    if count is None:
        count = _exclude_disabled_sources(
            Market.objects.filter(
                status=Market.Status.OPEN,
                canonical_category_slug=world_cup.slug,
            )
        ).count()
    return [{"category": world_cup, "count": count}, *summaries]


def get_market_hub_category_summaries():
    """Category cards for the markets hub — always shows main topics, Polymarket-like order."""
    summaries = get_category_summaries(include_empty=True)
    order = {slug: index for index, slug in enumerate(MARKET_HUB_CATEGORY_SLUG_ORDER)}
    summaries.sort(
        key=lambda item: (
            order.get(item["category"].slug, len(MARKET_HUB_CATEGORY_SLUG_ORDER)),
            -item["count"],
            item["category"].name,
        )
    )
    return summaries


def get_markets_list(*, status=None, category=None, search=None, source=None):
    qs = _market_card_queryset(_exclude_disabled_sources(Market.objects.all()))
    if status:
        qs = qs.filter(status=status)
    if category:
        qs = qs.filter(category__iexact=category)
    if source:
        qs = qs.filter(source=source)
    if search:
        qs = qs.filter(
            Q(title__icontains=search)
            | Q(description__icontains=search)
            | Q(category__icontains=search)
        )
    return qs


def get_markets_for_display(
    *,
    status=None,
    category=None,
    search=None,
    source=None,
    sort="",
    limit=100,
):
    """Return markets for list UI, blending sources when browsing open markets."""
    from markets.sort_options import SORT_ENDING_SOON, SORT_NEWEST, SORT_TRENDING, SORT_VOLUME

    qs = get_markets_list(status=status, category=category, search=search, source=source)
    normalized_sort = normalize_sort_filter(sort)
    effective_status = status or Market.Status.OPEN
    sorted_limit = limit
    if normalized_sort:
        sorted_limit = max(limit, getattr(settings, "MARKET_LIST_SORTED_LIMIT", 200))

    use_source_blend = (
        not normalized_sort
        and not search
        and not source
        and effective_status == Market.Status.OPEN
    )
    if use_source_blend:
        open_markets = list(qs.filter(status=Market.Status.OPEN))
        return blend_markets_by_source(open_markets, limit=limit)

    if normalized_sort == SORT_VOLUME:
        return list(
            qs.order_by("-volume_total", "-updated_at")[:sorted_limit]
        )

    if normalized_sort == SORT_NEWEST:
        return list(qs.order_by("-created_at", "-updated_at")[:sorted_limit])

    if normalized_sort == SORT_ENDING_SOON:
        markets = list(qs)
        return sort_markets(markets, sort=normalized_sort)[:sorted_limit]

    if normalized_sort == SORT_TRENDING:
        markets = list(qs)
        return sort_markets(markets, sort=normalized_sort)[:sorted_limit]

    markets = list(qs)
    if normalized_sort:
        markets = sort_markets(markets, sort=normalized_sort)
    else:
        markets.sort(key=lambda market: market.updated_at, reverse=True)
    return markets[:sorted_limit]


def get_world_cup_match_markets_queryset(*, source=""):
    """Open World Cup match markets ordered by kickoff."""
    qs = _market_card_queryset(
        Market.objects.filter(
            status=Market.Status.OPEN,
            canonical_category_slug=FIFA_WORLD_CUP_CATEGORY_SLUG,
        )
    )
    if source:
        qs = qs.filter(source=source)
    return qs.order_by("close_date", "title")


def get_market_categories():
    return (
        Market.objects.exclude(category="")
        .values_list("category", flat=True)
        .distinct()
        .order_by("category")
    )
