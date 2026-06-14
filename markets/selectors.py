import random
from collections import Counter, defaultdict

from datetime import datetime, timezone as dt_timezone

from django.db import connection
from django.db.models import Count, DateTimeField, F, Q
from django.db.models.functions import Coalesce
from django.utils import timezone

from markets.categories import (
    CANONICAL_CATEGORIES,
    FIFA_WORLD_CUP_CATEGORY_SLUG,
    OTHER_CATEGORY,
    get_category_for_slug,
)
from markets.browse_areas import (
    WORLD_CUP_GAMES_AREA_SLUG,
    get_browse_area,
    get_browse_areas_for_category,
    market_matches_browse_area,
)
from markets.models import Market
from markets.sort_options import market_volume, normalize_sort_filter, sort_markets

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
)
CATEGORY_BROWSE_LIMIT = 48
MARKET_CARD_DEFER_FIELDS = (
    "description",
    "polymarket_raw",
    "polymarket_event_raw",
)


def _market_card_queryset(qs):
    return qs.defer(*MARKET_CARD_DEFER_FIELDS)


def market_card_queryset(qs):
    """Lightweight queryset for market cards (skips large text fields)."""
    return _market_card_queryset(qs)


def _exclude_disabled_sources(markets):
    excluded = {Market.Source.MANUAL}
    if isinstance(markets, list):
        return [market for market in markets if market.source not in excluded]
    return markets.exclude(source__in=excluded)


def _public_market_filter(qs):
    """Public listings: enabled sources only, no orphan Polymarket legs."""
    from markets.composite_redirect import exclude_orphan_polymarket_legs

    return exclude_orphan_polymarket_legs(_exclude_disabled_sources(qs))


def open_market_q():
    """Markets with local status ``OPEN`` (may still be non-forecastable)."""
    return Q(status=Market.Status.OPEN)


def discoverable_market_q(*, now=None):
    """Markets shown in browse/hub/category listings — same rules as ``is_forecastable``."""
    return forecastable_market_q(now=now)


def forecastable_market_q(*, now=None):
    """Database equivalent of ``Market.is_forecastable`` for list/count queries."""
    now = now or timezone.now()
    return (
        Q(status=Market.Status.OPEN)
        & Q(accepting_orders=True)
        & (Q(close_date__isnull=True) | Q(close_date__gt=now))
        & (Q(game_start_time__isnull=True) | Q(game_start_time__gt=now))
    )


def normalize_category_filter(category):
    """Resolve category URL/input values to canonical category slugs."""
    value = (category or "").strip()
    if not value:
        return ""
    if get_category_for_slug(value):
        return value
    lowered = value.casefold()
    for candidate in (*CANONICAL_CATEGORIES, OTHER_CATEGORY):
        if (
            candidate.slug.casefold() == lowered
            or str(candidate.name).casefold() == lowered
            or lowered in candidate.category_names
        ):
            return candidate.slug
    return ""


def _chronological_far_future() -> datetime:
    return datetime(9999, 12, 31, 23, 59, 59, tzinfo=dt_timezone.utc)


def market_event_datetime(market):
    """Primary chronological key: scheduled start, else market close."""
    return market.game_start_time or market.close_date


def sort_markets_chronologically(markets):
    """Sort an in-memory market list soonest event first; undated markets last."""
    far_future = _chronological_far_future()
    return sorted(
        markets,
        key=lambda market: (
            market_event_datetime(market) or far_future,
            (market.title or "").casefold(),
        ),
    )


def order_markets_chronologically(qs):
    """Queryset ordering: ``game_start_time`` then ``close_date``, then title."""
    return qs.annotate(
        event_at=Coalesce(
            F("game_start_time"),
            F("close_date"),
            output_field=DateTimeField(),
        )
    ).order_by(F("event_at").asc(nulls_last=True), "title")


def _sort_markets_by_volume(markets):
    if isinstance(markets, list):
        return sorted(
            markets,
            key=lambda market: (market_volume(market), market.updated_at),
            reverse=True,
        )
    return markets.order_by("-volume_total", "-updated_at")


def blend_markets_by_source(markets, *, limit=CATEGORY_BROWSE_LIMIT):
    """Order markets by trading volume for browse listings."""
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


def _canonical_category_browse_q(category_slug):
    """ORM filter for markets shown on a category browse page."""
    category = get_category_for_slug(category_slug)
    if category is None:
        return None
    q = Q(canonical_category_slug=category.slug)
    # World Cup match forecasts are canonically ``fifa-world-cup-2026`` but
    # belong under Sports as the ``world-cup-games`` sub-area.
    if category_slug == "sports":
        q |= Q(canonical_category_slug=FIFA_WORLD_CUP_CATEGORY_SLUG)
    return q


def _apply_market_text_search(qs, search):
    query = (search or "").strip()
    if not query:
        return qs
    return qs.filter(
        Q(title__icontains=query)
        | Q(title_es__icontains=query)
        | Q(description__icontains=query)
        | Q(description_es__icontains=query)
        | Q(category__icontains=query)
    )


def _filter_queryset_by_browse_area(qs, *, category_slug, area_slug):
    """Filter a queryset to markets in a browse sub-area (portable across DB backends)."""
    area = get_browse_area(category_slug, area_slug)
    if area is None:
        return qs
    if category_slug == "sports" and area_slug == WORLD_CUP_GAMES_AREA_SLUG:
        return qs.filter(canonical_category_slug=FIFA_WORLD_CUP_CATEGORY_SLUG)
    if connection.vendor == "postgresql":
        return qs.filter(browse_area_slugs__contains=[area_slug])
    matching_pks = [
        pk
        for pk, slugs in qs.values_list("pk", "browse_area_slugs")
        if area_slug in (slugs or [])
    ]
    return qs.filter(pk__in=matching_pks)


def get_category_browse_queryset(
    *,
    category_slug,
    area_slug=None,
    search=None,
    source=None,
):
    """Queryset for paginated category browse (cards + search)."""
    category_q = _canonical_category_browse_q(category_slug)
    if category_q is None:
        return Market.objects.none()

    # When searching, include every locally-open market in the pool — same
    # spirit as ``/markets/all/`` — not only forecastable rows.
    visibility_q = open_market_q() if search else discoverable_market_q()

    qs = _public_market_filter(
        _market_card_queryset(
            Market.objects.filter(visibility_q).filter(category_q)
        )
    )

    if area_slug:
        qs = _filter_queryset_by_browse_area(
            qs,
            category_slug=category_slug,
            area_slug=area_slug,
        )
    if search:
        qs = _apply_market_text_search(qs, search)
    if source:
        qs = qs.filter(source=source)
    return order_markets_chronologically(qs)


def filter_markets_by_search(*, markets, search):
    """Filter an in-memory market list by title, description, or category text.

    Description fields are read only when already loaded on the instance. On card
    querysets ``description`` is deferred, and touching it per row would trigger
    an N+1 fetch, so it is skipped there (titles/category still match).
    """
    query = (search or "").strip()
    if not query:
        return markets
    needle = query.casefold()
    filtered = []
    for market in markets:
        loaded = market.__dict__
        haystacks = [
            market.display_title or "",
            loaded.get("title") or "",
            loaded.get("title_es") or "",
            loaded.get("category") or "",
        ]
        # Only include description fields that are already loaded (avoid N+1).
        for field in ("description", "description_es"):
            if field in loaded:
                haystacks.append(loaded[field] or "")
        if any(needle in value.casefold() for value in haystacks):
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
    """Markets for category browse cards, ordered soonest event first."""
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
    return sort_markets_chronologically(markets)[:limit]


def get_open_markets_by_canonical_category(*, category_slug, limit=None):
    """Return open markets for a canonical browse category, ordered chronologically."""
    category_q = _canonical_category_browse_q(category_slug)
    if category_q is None:
        return []

    qs = _public_market_filter(
        _market_card_queryset(
            Market.objects.filter(
                discoverable_market_q(),
            ).filter(category_q)
        )
    )
    qs = order_markets_chronologically(qs)

    if limit is not None:
        return list(qs[:limit])
    return list(qs)


def get_browse_area_summaries(*, category_slug, markets=None):
    """Count open markets per sub-area; only areas with at least one market.

    Uses the denormalized ``browse_area_slugs`` column instead of the deferred
    raw JSON payloads. When ``markets`` is not supplied, counts come from a
    single lightweight query that selects only that column (no N+1, no big
    payload transfer).
    """
    areas = get_browse_areas_for_category(category_slug)
    if not areas:
        return []

    counts = Counter()
    if markets is None:
        category_q = _canonical_category_browse_q(category_slug)
        if category_q is None:
            return []
        membership_rows = _public_market_filter(
            Market.objects.filter(
                discoverable_market_q(),
            ).filter(category_q)
        ).values_list("browse_area_slugs", "canonical_category_slug")
        wc_count = 0
        for slugs, canonical_slug in membership_rows:
            counts.update(slugs or ())
            if canonical_slug == FIFA_WORLD_CUP_CATEGORY_SLUG:
                wc_count += 1
        if category_slug == "sports" and wc_count:
            counts[WORLD_CUP_GAMES_AREA_SLUG] = wc_count
    else:
        for market in markets:
            counts.update(market.browse_area_slugs or ())
        if category_slug == "sports":
            wc_count = sum(
                1
                for market in markets
                if (getattr(market, "canonical_category_slug", "") or "")
                == FIFA_WORLD_CUP_CATEGORY_SLUG
            )
            if wc_count:
                counts[WORLD_CUP_GAMES_AREA_SLUG] = wc_count

    summaries = [
        {"area": area, "count": counts[area.slug]}
        for area in areas
        if counts[area.slug]
    ]
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
        _public_market_filter(Market.objects.filter(discoverable_market_q()))
        .values("canonical_category_slug")
        .annotate(count=Count("id"))
    ):
        slug = row["canonical_category_slug"] or OTHER_CATEGORY.slug
        counts[slug] = counts.get(slug, 0) + row["count"]

    wc_count = counts.get(FIFA_WORLD_CUP_CATEGORY_SLUG, 0)
    if wc_count:
        counts["sports"] = counts.get("sports", 0) + wc_count

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
    """Featured shortcut to World Cup match forecasts under Sports."""
    world_cup = get_category_for_slug(FIFA_WORLD_CUP_CATEGORY_SLUG)
    if world_cup is None:
        return summaries

    summaries = [item for item in summaries if item["category"].slug != world_cup.slug]
    count = counts.get(world_cup.slug, 0)
    if not count:
        count = _public_market_filter(
            Market.objects.filter(
                discoverable_market_q(),
                canonical_category_slug=world_cup.slug,
            )
        ).count()
    if not count:
        return summaries
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


def get_markets_list(*, status=None, category=None, search=None, source=None, ending_within_hours=None):
    qs = _market_card_queryset(_public_market_filter(Market.objects.all()))
    if status == Market.Status.OPEN:
        qs = qs.filter(discoverable_market_q())
    elif status:
        qs = qs.filter(status=status)
    category_slug = normalize_category_filter(category)
    if category_slug:
        category_q = _canonical_category_browse_q(category_slug)
        if category_q is not None:
            qs = qs.filter(category_q)
    if source:
        qs = qs.filter(source=source)
    if search:
        qs = _apply_market_text_search(qs, search)
    if ending_within_hours:
        from datetime import timedelta

        from django.utils import timezone

        now = timezone.now()
        qs = qs.filter(
            close_date__isnull=False,
            close_date__gte=now,
            close_date__lte=now + timedelta(hours=ending_within_hours),
        )
    return qs


def apply_markets_list_ordering(qs, *, sort="", ending_within_hours=None):
    """Apply list-page sort order to a filtered markets queryset."""
    from markets.sort_options import (
        SORT_ENDING_SOON,
        SORT_LIQUIDITY,
        SORT_NEWEST,
        SORT_TRENDING,
        SORT_VOLUME,
        normalize_sort_filter,
    )

    normalized_sort = normalize_sort_filter(sort)
    if ending_within_hours and not normalized_sort:
        return qs.order_by(F("close_date").asc(nulls_last=True), "-volume_total")
    if normalized_sort == SORT_VOLUME:
        return qs.order_by("-volume_total", "-updated_at")
    if normalized_sort == SORT_NEWEST:
        return qs.order_by("-created_at", "-updated_at")
    if normalized_sort == SORT_TRENDING:
        return qs.order_by("-volume_24h", "-updated_at")
    if normalized_sort == SORT_LIQUIDITY:
        return qs.order_by("-liquidity_total", "-volume_total", "-updated_at")
    if normalized_sort == SORT_ENDING_SOON:
        return qs.order_by(F("close_date").asc(nulls_last=True), "-volume_total")
    if normalized_sort:
        return qs.order_by("-volume_total", "-updated_at")
    return qs.order_by("-volume_total", "-updated_at")


def get_markets_for_display(
    *,
    status=None,
    category=None,
    search=None,
    source=None,
    sort="",
    ending_within_hours=None,
    limit=100,
):
    """Return markets for list UI with consistent filters and ordering."""
    from markets.sort_options import normalize_sort_filter

    # An "ending soon" window only makes sense for live (open) markets.
    if ending_within_hours:
        status = Market.Status.OPEN

    qs = get_markets_list(
        status=status,
        category=category,
        search=search,
        source=source,
        ending_within_hours=ending_within_hours,
    )
    normalized_sort = normalize_sort_filter(sort)

    if ending_within_hours and not normalized_sort:
        return list(
            apply_markets_list_ordering(
                qs,
                sort=sort,
                ending_within_hours=ending_within_hours,
            )[:limit]
        )

    return list(
        apply_markets_list_ordering(
            qs,
            sort=sort,
            ending_within_hours=ending_within_hours,
        )[:limit]
    )


def get_world_cup_match_markets_queryset(*, source=""):
    """Open World Cup match markets ordered by kickoff."""
    qs = _public_market_filter(
        _market_card_queryset(
            Market.objects.filter(
                discoverable_market_q(),
                canonical_category_slug=FIFA_WORLD_CUP_CATEGORY_SLUG,
            )
        )
    )
    if source:
        qs = qs.filter(source=source)
    return order_markets_chronologically(qs)


def get_markets_resolving_soon(*, within_hours=72, limit=8):
    """Open markets whose close_date is imminent — drives urgency/FOMO UI.

    Ordered soonest-first. Excludes already-closed/resolved markets and those
    with no close_date. Read-only; does not mutate market status.
    """
    from datetime import timedelta

    from django.utils import timezone

    now = timezone.now()
    cutoff = now + timedelta(hours=within_hours)
    qs = _public_market_filter(
        _market_card_queryset(
            Market.objects.filter(
                forecastable_market_q(now=now),
                close_date__isnull=False,
                close_date__gte=now,
                close_date__lte=cutoff,
            )
        )
    ).order_by("close_date")
    return list(qs[:limit])


def get_popular_open_markets(*, limit=6):
    """Highest-volume open markets — good first-forecast suggestions for onboarding."""
    qs = _public_market_filter(
        _market_card_queryset(Market.objects.filter(forecastable_market_q()))
    ).order_by("-volume_total", "-created_at")
    return list(qs[:limit])


LANDING_TAPE_POOL_SIZE = 100
LANDING_TAPE_DEFAULT_LIMIT = 20


def get_landing_tape_markets(*, limit=LANDING_TAPE_DEFAULT_LIMIT, pool_size=LANDING_TAPE_POOL_SIZE):
    """Random discoverable markets with Polymarket images — landing marquee tape."""
    qs = _public_market_filter(
        _market_card_queryset(
            Market.objects.filter(
                discoverable_market_q(),
            ).exclude(card_image_url="")
        )
    ).order_by("-volume_total", "-created_at")
    pool = list(qs[:pool_size])
    if not pool:
        return []
    if len(pool) <= limit:
        random.shuffle(pool)
        return pool
    return random.sample(pool, limit)


def get_market_categories():
    return CANONICAL_CATEGORIES + (OTHER_CATEGORY,)
