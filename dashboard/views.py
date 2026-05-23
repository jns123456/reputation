from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

from accounts.selectors import get_top_popular_users, get_top_predictors
from markets.categories import get_category_for_slug
from markets.selectors import get_category_summaries, get_open_markets_by_canonical_category
from predictions.models import Prediction

CATEGORY_SUMMARIES_CACHE_KEY = "landing_category_summaries"


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


def category_browse(request, slug):
    category = get_category_for_slug(slug)
    if category is None:
        raise Http404("Category not found")

    all_markets = get_open_markets_by_canonical_category(category_slug=slug)
    markets = all_markets[:48]
    return render(
        request,
        "dashboard/category_browse.html",
        {
            "category": category,
            "markets": markets,
            "market_count": len(all_markets),
        },
    )


@login_required
def home(request):
    user_predictions = Prediction.objects.filter(user=request.user).select_related("market")[:10]
    profile = request.user.profile
    return render(
        request,
        "dashboard/home.html",
        {
            "recent_predictions": user_predictions,
            "profile": profile,
        },
    )


def reputation_leaderboard(request):
    leaders = get_top_predictors(50)
    return render(request, "dashboard/reputation_leaderboard.html", {"leaders": leaders})


def popularity_leaderboard(request):
    leaders = get_top_popular_users(50)
    return render(request, "dashboard/popularity_leaderboard.html", {"leaders": leaders})
