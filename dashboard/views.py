from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render

from accounts.category_selectors import (
    get_top_popular_users_by_category,
    get_top_predictors_by_category,
    validate_category_slug,
)
from accounts.selectors import get_top_popular_users, get_top_predictors
from dashboard.forum_context import get_forum_page_context
from integrations.services import sync_binary_markets_by_tag
from markets.categories import get_all_chart_categories, get_category_for_slug
from markets.browse_areas import get_browse_area
from markets.selectors import (
    filter_markets_by_browse_area,
    get_browse_area_summaries,
    get_category_summaries,
    get_open_markets_by_canonical_category,
)

CATEGORY_SUMMARIES_CACHE_KEY = "landing_category_summaries"
CATEGORY_SYNC_CACHE_PREFIX = "category_synced:"


def _load_category_summaries():
    summaries = cache.get(CATEGORY_SUMMARIES_CACHE_KEY)
    if summaries is None:
        summaries = get_category_summaries(include_empty=False)
        cache.set(CATEGORY_SUMMARIES_CACHE_KEY, summaries, settings.POLYMARKET_ECONOMY_CACHE_SECONDS)
    return summaries


def landing(request):
    category_summaries = _load_category_summaries()
    top_predictors = get_top_predictors(5)
    return render(
        request,
        "dashboard/landing.html",
        {
            "category_summaries": category_summaries,
            "top_predictors": top_predictors,
        },
    )


def _sync_category_markets_if_needed(category):
    """Import fresh markets from Polymarket when browsing a tagged category."""
    if not category.polymarket_tag:
        return

    cache_key = f"{CATEGORY_SYNC_CACHE_PREFIX}{category.slug}"
    if cache.get(cache_key):
        return

    sync_binary_markets_by_tag(
        tag_slug=category.polymarket_tag,
        default_category=category.name,
        limit=48,
    )
    cache.delete(CATEGORY_SUMMARIES_CACHE_KEY)
    cache.set(cache_key, True, settings.POLYMARKET_ECONOMY_CACHE_SECONDS)


def category_browse(request, slug):
    category = get_category_for_slug(slug)
    if category is None:
        raise Http404("Category not found")

    _sync_category_markets_if_needed(category)

    total_markets = get_open_markets_by_canonical_category(category_slug=slug)
    area_summaries = get_browse_area_summaries(category_slug=slug, markets=total_markets)

    area_slug = request.GET.get("area", "").strip()
    active_area = get_browse_area(slug, area_slug) if area_slug else None
    display_markets = total_markets
    if active_area:
        display_markets = filter_markets_by_browse_area(
            markets=total_markets,
            category_slug=slug,
            area_slug=area_slug,
        )

    markets = display_markets[:48]
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
