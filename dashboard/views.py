from django.conf import settings
from django.core.cache import cache
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
import logging
from datetime import timedelta

from accounts.category_selectors import (
    validate_category_slug,
)
from accounts.selectors import get_top_predictors
from dashboard.forecasts_context import get_forecasts_page_context
from dashboard.leaderboard_cache import get_cached_top_popular_users, get_cached_top_predictors
from integrations.celery_utils import celery_broker_available, enqueue_category_sync
from markets.categories import FIFA_WORLD_CUP_CATEGORY_SLUG, get_all_chart_categories, get_category_for_slug
from markets.browse_areas import WORLD_CUP_GAMES_AREA_SLUG, get_browse_area
from markets.source_filters import build_browse_clear_search_url, build_source_filter_urls, normalize_source_filter
from markets.selectors import (
    get_browse_area_summaries,
    get_category_browse_queryset,
    get_category_summaries,
    get_world_cup_match_markets_queryset,
)
from predictions.selectors import attach_user_forecasts_to_markets

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
    if not category.polymarket_tag:
        return

    poly_cache_key = f"{CATEGORY_SYNC_CACHE_PREFIX}polymarket:{category.slug}"
    if cache.get(poly_cache_key):
        return

    if not enqueue_category_sync(category.slug):
        logger.debug("Category sync for %s not queued; Celery broker unavailable", category.slug)
        return

    cache.set(poly_cache_key, True, settings.MARKET_SYNC_CACHE_SECONDS)


def category_browse(request, slug):
    category = get_category_for_slug(slug)
    if category is None:
        raise Http404("Category not found")

    if slug == FIFA_WORLD_CUP_CATEGORY_SLUG:
        query = request.GET.copy()
        query["area"] = WORLD_CUP_GAMES_AREA_SLUG
        destination = reverse("dashboard:category_browse", kwargs={"slug": "sports"})
        encoded = query.urlencode()
        return redirect(destination if not encoded else f"{destination}?{encoded}")

    _enqueue_category_sync_if_needed(category)

    area_slug = request.GET.get("area", "").strip()
    search = request.GET.get("q", "").strip()
    source = normalize_source_filter(request.GET.get("source", ""))
    world_cup_match_layout = (
        slug == "sports" and area_slug == WORLD_CUP_GAMES_AREA_SLUG and not search
    )

    active_area = get_browse_area(slug, area_slug) if area_slug else None
    browse_base_url = reverse("dashboard:category_browse", kwargs={"slug": slug})
    area_summaries = get_browse_area_summaries(category_slug=slug)
    total_market_count = get_category_browse_queryset(category_slug=slug).count()

    if world_cup_match_layout:
        browse_qs = get_world_cup_match_markets_queryset(source=source)
        page_size = settings.WORLD_CUP_MATCHES_PER_PAGE
    else:
        browse_qs = get_category_browse_queryset(
            category_slug=slug,
            area_slug=area_slug or None,
            search=search or None,
            source=source or None,
        )
        page_size = settings.CATEGORY_BROWSE_PAGE_SIZE

    market_count = browse_qs.count()
    paginator = Paginator(browse_qs, page_size)
    page_obj = paginator.get_page(request.GET.get("page"))
    markets = attach_user_forecasts_to_markets(request.user, list(page_obj.object_list))
    source_filter_urls = build_source_filter_urls(
        base_url=browse_base_url,
        active_source=source,
        extra={"area": area_slug, "q": search},
    )
    return render(
        request,
        "dashboard/category_browse.html",
        {
            "category": category,
            "markets": markets,
            "market_count": market_count,
            "total_market_count": total_market_count,
            "page_obj": page_obj,
            "pagination_query": _pagination_extra_query(request),
            "area_summaries": area_summaries,
            "active_area": active_area,
            "active_area_slug": active_area.slug if active_area else "",
            "active_source": source,
            "search_query": search,
            "world_cup_match_layout": world_cup_match_layout,
            "source_filter_urls": source_filter_urls,
            "clear_search_url": build_browse_clear_search_url(
                base_url=browse_base_url,
                source=source,
                area=area_slug,
            ),
            "is_following_topic": _is_following_topic(request.user, slug),
        },
    )


def _is_following_topic(user, category_slug):
    from accounts.follow_selectors import is_following_topic

    return is_following_topic(user=user, category_slug=category_slug)


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
    markets = attach_user_forecasts_to_markets(request.user, list(page_obj.object_list))
    source_filter_urls = build_source_filter_urls(
        base_url=reverse("dashboard:category_browse", kwargs={"slug": FIFA_WORLD_CUP_CATEGORY_SLUG}),
        active_source=source,
    )
    return {
        "category": category,
        "markets": markets,
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


def _reputation_leaderboard_context(request, *, category=None):
    from dashboard.leaderboard_cache import get_cached_top_predictors_for_period
    from reputation.leaderboard import build_leaderboard_rows
    from reputation.period_leaderboard import PERIOD_ALL, normalize_leaderboard_period
    from reputation.ranking_modes import ABSOLUTE, get_relative_ranking_min_scored_forecasts, normalize_reputation_ranking_mode

    ranking_mode = normalize_reputation_ranking_mode(request.GET.get("mode"))
    period = normalize_leaderboard_period(request.GET.get("period"))

    if period != PERIOD_ALL:
        leaders = get_cached_top_predictors_for_period(
            period=period,
            category_slug=category.slug if category else "",
            limit=50,
            mode=ranking_mode,
        )
    elif category:
        leaders = get_cached_top_predictors(
            category_slug=category.slug,
            limit=50,
            mode=ranking_mode,
        )
    else:
        leaders = get_cached_top_predictors(limit=50, mode=ranking_mode)

    if ranking_mode == ABSOLUTE:
        hero_description_key = "category_absolute" if category else "global_absolute"
    else:
        hero_description_key = "category_relative" if category else "global_relative"

    return {
        "leaders": leaders,
        "leaderboard_rows": build_leaderboard_rows(leaders, ranking_mode=ranking_mode),
        "category": category,
        "chart_categories": get_all_chart_categories(),
        "is_category_leaderboard": category is not None,
        "ranking_mode": ranking_mode,
        "leaderboard_period": period,
        "hero_description_key": hero_description_key,
        "relative_ranking_min_scored": get_relative_ranking_min_scored_forecasts(),
    }


def reputation_leaderboard(request):
    category_slug = request.GET.get("category", "").strip()
    category = validate_category_slug(category_slug) if category_slug else None
    if category_slug and category is None:
        raise Http404("Category not found")

    return render(
        request,
        "dashboard/reputation_leaderboard.html",
        _reputation_leaderboard_context(request, category=category),
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


def weekly_contest(request):
    """Weekly reputation contest — calendar-week standings with cash prizes."""
    from django.http import Http404

    from dashboard.leaderboard_cache import get_cached_top_predictors_for_week
    from reputation.leaderboard import build_leaderboard_rows
    from reputation.ranking_modes import ABSOLUTE, normalize_reputation_ranking_mode
    from reputation.weekly_contest_services import (
        current_week_code,
        filter_weekly_contest_qualified,
        get_weekly_contest_min_scored_forecasts,
        qualifies_for_weekly_contest,
        week_date_range,
        weekly_contest_enabled,
        weekly_contest_prize_usd,
    )

    if not weekly_contest_enabled():
        raise Http404()

    ranking_mode = normalize_reputation_ranking_mode(request.GET.get("mode"))
    week_code = request.GET.get("week", "").strip() or current_week_code()

    leaders = filter_weekly_contest_qualified(
        get_cached_top_predictors_for_week(
            week_code=week_code,
            limit=100,
            mode=ranking_mode,
        )
    )[:50]

    if ranking_mode == ABSOLUTE:
        hero_description_key = "weekly_absolute"
    else:
        hero_description_key = "weekly_relative"

    since, until = week_date_range(week_code)
    week_start = since
    week_end = until - timedelta(seconds=1)

    return render(
        request,
        "dashboard/weekly_contest.html",
        {
            "leaders": leaders,
            "leaderboard_rows": build_leaderboard_rows(
                leaders,
                ranking_mode=ranking_mode,
                qualifies_fn=qualifies_for_weekly_contest,
            ),
            "ranking_mode": ranking_mode,
            "week_code": week_code,
            "week_start": week_start,
            "week_end": week_end,
            "is_current_week": week_code == current_week_code(),
            "prize_usd": weekly_contest_prize_usd(),
            "hero_description_key": hero_description_key,
            "weekly_contest_min_scored": get_weekly_contest_min_scored_forecasts(),
            "is_category_leaderboard": False,
        },
    )


@login_required
def weekly_contest_dismiss_announcement(request):
    """Permanently hide the weekly contest login modal for this user."""
    from django.http import HttpResponseNotAllowed, JsonResponse
    from reputation.weekly_contest_services import dismiss_weekly_contest_announcement

    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    dismiss_weekly_contest_announcement(user=request.user)
    return JsonResponse({"ok": True})


def agent_arena(request):
    """Agent Arena — reputation leaderboard restricted to declared AI agents."""
    from dashboard.leaderboard_cache import (
        get_cached_top_agent_predictors,
        get_cached_top_predictors_for_period,
    )
    from reputation.leaderboard import build_leaderboard_rows
    from reputation.period_leaderboard import PERIOD_ALL, normalize_leaderboard_period
    from reputation.ranking_modes import get_relative_ranking_min_scored_forecasts, normalize_reputation_ranking_mode

    ranking_mode = normalize_reputation_ranking_mode(request.GET.get("mode"))
    period = normalize_leaderboard_period(request.GET.get("period"))

    if period != PERIOD_ALL:
        leaders = get_cached_top_predictors_for_period(
            period=period,
            limit=50,
            mode=ranking_mode,
            agents_only=True,
        )
    else:
        leaders = get_cached_top_agent_predictors(limit=50, mode=ranking_mode)

    return render(
        request,
        "dashboard/agent_arena.html",
        {
            "leaders": leaders,
            "leaderboard_rows": build_leaderboard_rows(leaders, ranking_mode=ranking_mode),
            "ranking_mode": ranking_mode,
            "leaderboard_period": period,
            "is_category_leaderboard": False,
            "relative_ranking_min_scored": get_relative_ranking_min_scored_forecasts(),
        },
    )


def reputation_leaderboard_category(request, slug):
    category = get_category_for_slug(slug)
    if category is None:
        raise Http404("Category not found")
    return render(
        request,
        "dashboard/reputation_leaderboard.html",
        _reputation_leaderboard_context(request, category=category),
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

    from accounts.mission_services import get_daily_missions

    missions = get_daily_missions(request.user)
    context["daily_missions"] = missions
    context["completed_mission_count"] = sum(1 for card in missions if card["completed"])
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
