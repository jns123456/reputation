from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
import logging

from accounts.category_selectors import (
    get_top_popular_users_by_category,
    get_top_predictors_by_category,
    validate_category_slug,
)
from accounts.selectors import get_top_popular_users, get_top_predictors
from dashboard.forum_context import get_forum_page_context
from integrations.celery_utils import enqueue_category_sync
from markets.categories import get_all_chart_categories, get_category_for_slug
from markets.browse_areas import get_browse_area
from markets.source_filters import build_source_filter_urls, normalize_source_filter
from markets.selectors import (
    filter_markets_by_browse_area,
    get_browse_area_summaries,
    get_category_display_markets,
    get_category_summaries,
    get_open_markets_by_canonical_category,
)

logger = logging.getLogger(__name__)

CATEGORY_SUMMARIES_CACHE_KEY = "landing_category_summaries"
CATEGORY_SYNC_CACHE_PREFIX = "category_synced:"


def _load_category_summaries():
    summaries = cache.get(CATEGORY_SUMMARIES_CACHE_KEY)
    if summaries is None:
        summaries = get_category_summaries(include_empty=False)
        cache.set(CATEGORY_SUMMARIES_CACHE_KEY, summaries, settings.MARKET_SYNC_CACHE_SECONDS)
    return summaries


def landing(request):
    category_summaries = _load_category_summaries()
    top_predictors = get_top_predictors(5)
    source = normalize_source_filter(request.GET.get("source", ""))
    landing_source_filter_urls = build_source_filter_urls(
        base_url=reverse("dashboard:landing"),
        active_source=source,
    )
    return render(
        request,
        "dashboard/landing.html",
        {
            "category_summaries": category_summaries,
            "top_predictors": top_predictors,
            "landing_source_filter_urls": landing_source_filter_urls,
            "active_source": source,
        },
    )


def _enqueue_category_sync_if_needed(category):
    """Queue background sync; never block the HTTP response."""
    if not category.polymarket_tag and not category.kalshi_series_tickers:
        return

    poly_cache_key = f"{CATEGORY_SYNC_CACHE_PREFIX}polymarket:{category.slug}"
    kalshi_cache_key = f"{CATEGORY_SYNC_CACHE_PREFIX}kalshi:{category.slug}"
    poly_due = category.polymarket_tag and not cache.get(poly_cache_key)
    kalshi_due = category.kalshi_series_tickers and not cache.get(kalshi_cache_key)

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

    enqueue_category_sync(category.slug)


def category_browse(request, slug):
    category = get_category_for_slug(slug)
    if category is None:
        raise Http404("Category not found")

    _enqueue_category_sync_if_needed(category)

    area_slug = request.GET.get("area", "").strip()
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

    markets = get_category_display_markets(
        category_slug=slug,
        source=source or None,
        area_slug=area_slug or None,
        markets=total_markets,
    )
    source_filter_urls = build_source_filter_urls(
        base_url=reverse("dashboard:category_browse", kwargs={"slug": slug}),
        active_source=source,
        extra={"area": area_slug},
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
            "source_filter_urls": source_filter_urls,
        },
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
        leaders = get_top_predictors_by_category(category.slug, 50)
    else:
        leaders = get_top_predictors(50)

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
        leaders = get_top_popular_users_by_category(category.slug, 50)
    else:
        leaders = get_top_popular_users(50)

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
    leaders = get_top_predictors_by_category(category.slug, 50)
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
    leaders = get_top_popular_users_by_category(category.slug, 50)
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


def faq(request):
    return render(request, "dashboard/faq.html")


def forum(request):
    context = get_forum_page_context(
        request=request,
        market_slug=request.GET.get("market", ""),
    )
    return render(request, "dashboard/forum.html", context)


def forum_feed(request):
    context = get_forum_page_context(
        request=request,
        market_slug=request.GET.get("market", ""),
    )
    return render(request, "dashboard/partials/forum_feed.html", context)
