from django.conf import settings
from django.core.cache import cache
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
import logging

from accounts.category_selectors import (
    validate_category_slug,
)
from accounts.selectors import get_top_predictors
from dashboard.forecasts_context import get_forecasts_page_context
from dashboard.leaderboard_cache import get_cached_top_popular_users, get_cached_top_predictors
from integrations.celery_utils import celery_broker_available, enqueue_category_sync
from markets.categories import FIFA_WORLD_CUP_CATEGORY_SLUG, get_all_chart_categories, get_category_for_slug
from markets.browse_areas import get_browse_area
from markets.source_filters import build_browse_clear_search_url, build_source_filter_urls, kalshi_enabled, normalize_source_filter
from markets.selectors import (
    filter_markets_by_browse_area,
    filter_markets_by_search,
    get_browse_area_summaries,
    get_category_display_markets,
    get_category_summaries,
    get_open_markets_by_canonical_category,
    get_world_cup_match_markets_queryset,
)

logger = logging.getLogger(__name__)

CATEGORY_SUMMARIES_CACHE_KEY = "landing_category_summaries"
CATEGORY_SYNC_CACHE_PREFIX = "category_synced:"
WORLD_CUP_SYNC_CACHE_KEY = f"{CATEGORY_SYNC_CACHE_PREFIX}polymarket:world-cup-games"
LANDING_TOP_PREDICTORS_CACHE_KEY = "landing_top_predictors"
LANDING_TOP_PREDICTORS_LIMIT = 5


def _load_category_summaries():
    summaries = cache.get(CATEGORY_SUMMARIES_CACHE_KEY)
    if summaries is None:
        summaries = get_category_summaries(include_empty=False)
        cache.set(CATEGORY_SUMMARIES_CACHE_KEY, summaries, settings.MARKET_SYNC_CACHE_SECONDS)
    return summaries


def _load_top_predictors(limit=LANDING_TOP_PREDICTORS_LIMIT):
    leaders = cache.get(LANDING_TOP_PREDICTORS_CACHE_KEY)
    if leaders is None:
        leaders = list(get_top_predictors(limit))
        cache.set(
            LANDING_TOP_PREDICTORS_CACHE_KEY,
            leaders,
            settings.LEADERBOARD_CACHE_SECONDS,
        )
    return leaders


def explore(request):
    from django.shortcuts import redirect

    query = request.GET.urlencode()
    target = reverse("markets:list")
    if query:
        target = f"{target}?{query}"
    return redirect(target)


def _enqueue_category_sync_if_needed(category):
    """Queue background sync; never block the HTTP response on external APIs."""
    has_poly = bool(category.polymarket_tag)
    has_kalshi = kalshi_enabled() and bool(category.kalshi_series_tickers)
    if not has_poly and not has_kalshi:
        return

    poly_cache_key = f"{CATEGORY_SYNC_CACHE_PREFIX}polymarket:{category.slug}"
    kalshi_cache_key = f"{CATEGORY_SYNC_CACHE_PREFIX}kalshi:{category.slug}"
    poly_due = has_poly and not cache.get(poly_cache_key)
    kalshi_due = has_kalshi and not cache.get(kalshi_cache_key)

    if not poly_due and not kalshi_due:
        return

    if poly_due:
        cache.set(poly_cache_key, True, settings.MARKET_SYNC_CACHE_SECONDS)
    if kalshi_due:
        cache.set(
            kalshi_cache_key,
            True,
            getattr(settings, "KALSHI_SYNC_CACHE_SECONDS", settings.MARKET_SYNC_CACHE_SECONDS),
        )

    if not enqueue_category_sync(category.slug):
        logger.debug("Category sync for %s not queued; Celery broker unavailable", category.slug)


def category_browse(request, slug):
    category = get_category_for_slug(slug)
    if category is None:
        raise Http404("Category not found")

    if slug == FIFA_WORLD_CUP_CATEGORY_SLUG:
        return world_cup_games(request, category=category)

    _enqueue_category_sync_if_needed(category)

    area_slug = request.GET.get("area", "").strip()
    search = request.GET.get("q", "").strip()
    source = normalize_source_filter(request.GET.get("source", ""))

    total_markets = get_open_markets_by_canonical_category(category_slug=slug)
    area_summaries = get_browse_area_summaries(category_slug=slug, markets=total_markets)

    active_area = get_browse_area(slug, area_slug) if area_slug else None
    display_markets = total_markets
    if active_area:
        display_markets = filter_markets_by_browse_area(
            markets=total_markets,
            category_slug=slug,
            area_slug=area_slug,
        )
    if source:
        display_markets = [market for market in display_markets if market.source == source]
    if search:
        display_markets = filter_markets_by_search(markets=display_markets, search=search)

    markets = get_category_display_markets(
        category_slug=slug,
        source=source or None,
        area_slug=area_slug or None,
        search=search or None,
        markets=total_markets,
    )
    source_filter_urls = build_source_filter_urls(
        base_url=reverse("dashboard:category_browse", kwargs={"slug": slug}),
        active_source=source,
        extra={"area": area_slug, "q": search},
    )
    return render(
        request,
        "dashboard/category_browse.html",
        {
            "category": category,
            "markets": markets,
            "market_count": len(display_markets),
            "total_market_count": len(total_markets),
            "area_summaries": area_summaries,
            "active_area": active_area,
            "active_area_slug": active_area.slug if active_area else "",
            "active_source": source,
            "search_query": search,
            "source_filter_urls": source_filter_urls,
            "clear_search_url": build_browse_clear_search_url(
                base_url=reverse("dashboard:category_browse", kwargs={"slug": slug}),
                source=source,
                area=area_slug,
            ),
        },
    )


def _pagination_extra_query(request, *, exclude=("page",)):
    query = request.GET.copy()
    for key in exclude:
        query.pop(key, None)
    return query.urlencode()


def _world_cup_games_context(request, *, category=None):
    category = category or get_category_for_slug(FIFA_WORLD_CUP_CATEGORY_SLUG)
    _enqueue_category_sync_if_needed(category)

    source = normalize_source_filter(request.GET.get("source", ""))
    queryset = get_world_cup_match_markets_queryset(source=source)
    total_count = queryset.count()
    paginator = Paginator(queryset, settings.WORLD_CUP_MATCHES_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))
    source_filter_urls = build_source_filter_urls(
        base_url=reverse("dashboard:category_browse", kwargs={"slug": FIFA_WORLD_CUP_CATEGORY_SLUG}),
        active_source=source,
    )
    return {
        "category": category,
        "markets": page_obj.object_list,
        "market_count": total_count,
        "page_obj": page_obj,
        "pagination_query": _pagination_extra_query(request),
        "active_source": source,
        "source_filter_urls": source_filter_urls,
    }


def world_cup_games(request, category=None):
    """Dedicated browse page for FIFA World Cup match forecasts (3-way results)."""
    return render(
        request,
        "dashboard/world_cup_games.html",
        _world_cup_games_context(request, category=category),
    )


@login_required
def home(request):
    return redirect("accounts:profile", username=request.user.username)


def reputation_leaderboard(request):
    category_slug = request.GET.get("category", "").strip()
    category = validate_category_slug(category_slug) if category_slug else None
    if category_slug and category is None:
        raise Http404("Category not found")

    if category:
        leaders = get_cached_top_predictors(category_slug=category.slug, limit=50)
    else:
        leaders = get_cached_top_predictors(limit=50)

    return render(
        request,
        "dashboard/reputation_leaderboard.html",
        {
            "leaders": leaders,
            "category": category,
            "chart_categories": get_all_chart_categories(),
            "is_category_leaderboard": category is not None,
        },
    )


def popularity_leaderboard(request):
    category_slug = request.GET.get("category", "").strip()
    category = validate_category_slug(category_slug) if category_slug else None
    if category_slug and category is None:
        raise Http404("Category not found")

    if category:
        leaders = get_cached_top_popular_users(category_slug=category.slug, limit=50)
    else:
        leaders = get_cached_top_popular_users(limit=50)

    return render(
        request,
        "dashboard/popularity_leaderboard.html",
        {
            "leaders": leaders,
            "category": category,
            "chart_categories": get_all_chart_categories(),
            "is_category_leaderboard": category is not None,
        },
    )


def reputation_leaderboard_category(request, slug):
    category = get_category_for_slug(slug)
    if category is None:
        raise Http404("Category not found")
    leaders = get_cached_top_predictors(category_slug=category.slug, limit=50)
    return render(
        request,
        "dashboard/reputation_leaderboard.html",
        {
            "leaders": leaders,
            "category": category,
            "chart_categories": get_all_chart_categories(),
            "is_category_leaderboard": True,
        },
    )


def popularity_leaderboard_category(request, slug):
    category = get_category_for_slug(slug)
    if category is None:
        raise Http404("Category not found")
    leaders = get_cached_top_popular_users(category_slug=category.slug, limit=50)
    return render(
        request,
        "dashboard/popularity_leaderboard.html",
        {
            "leaders": leaders,
            "category": category,
            "chart_categories": get_all_chart_categories(),
            "is_category_leaderboard": True,
        },
    )


def about(request):
    return render(request, "dashboard/about.html")


def legal(request):
    return render(request, "dashboard/legal.html")


def terms(request):
    return render(request, "dashboard/terms.html")


def faq(request):
    return render(request, "dashboard/faq.html")


RESOLVING_SOON_CACHE_KEY = "forecasts_resolving_soon"
RESOLVING_SOON_CACHE_SECONDS = 300


def _load_resolving_soon():
    markets = cache.get(RESOLVING_SOON_CACHE_KEY)
    if markets is None:
        from markets.selectors import get_markets_resolving_soon

        markets = get_markets_resolving_soon(within_hours=72, limit=8)
        cache.set(RESOLVING_SOON_CACHE_KEY, markets, RESOLVING_SOON_CACHE_SECONDS)
    return markets


def forecasts(request):
    context = get_forecasts_page_context(
        request=request,
        market_slug=request.GET.get("market", ""),
        sort=request.GET.get("sort", "recent"),
        page=request.GET.get("page", 1),
    )
    context["resolving_soon"] = _load_resolving_soon()
    return render(request, "dashboard/forecasts.html", context)


def forecasts_feed(request):
    context = get_forecasts_page_context(
        request=request,
        market_slug=request.GET.get("market", ""),
        sort=request.GET.get("sort", "recent"),
        page=request.GET.get("page", 1),
    )
    # Page 2+ requests only need the appended items + next sentinel.
    if context["feed_page"] > 1:
        return render(request, "dashboard/partials/forecasts_feed_page.html", context)
    return render(request, "dashboard/partials/forecasts_feed.html", context)
