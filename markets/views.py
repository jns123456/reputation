from urllib.parse import urlencode

from django.conf import settings
from django.core.cache import cache
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.bookmark_selectors import get_user_bookmarked_ids
from accounts.models import Bookmark
from comments.models import Vote
from comments.selectors import (
    attach_comment_votes,
    attach_vote_summaries_to_comments,
    collect_comment_ids,
    get_market_prediction_discussions,
    get_user_comment_votes,
    get_user_prediction_votes,
    get_vote_previews_for_targets,
    get_vote_summaries_for_targets,
)
from challenges.selectors import get_active_challenge_contexts_for_market
from integrations.polymarket.embed import build_polymarket_embed_context
from integrations.celery_utils import enqueue_market_refresh_if_stale
from markets.ending_filters import ENDING_WINDOW_CHOICES, ending_window_hours, normalize_ending_filter
from markets.models import Market
from markets.categories import get_category_for_slug
from markets.selectors import (
    apply_markets_list_ordering,
    get_market_categories,
    get_market_hub_category_summaries,
    get_markets_for_display,
    get_markets_list,
    normalize_category_filter,
)
from markets.sort_options import MARKET_SORT_CHOICES, normalize_sort_filter
from markets.source_filters import build_browse_clear_search_url, build_source_filter_urls, normalize_source_filter
from predictions.forms import ForecastForm
from predictions.selectors import get_market_predictions, get_user_active_prediction, attach_user_forecasts_to_markets
from reputation.services import calculate_reputation_stakes

MARKET_HUB_SUMMARIES_CACHE_KEY = "market_hub_category_summaries"


def _load_market_hub_summaries():
    summaries = cache.get(MARKET_HUB_SUMMARIES_CACHE_KEY)
    if summaries is None:
        summaries = get_market_hub_category_summaries()
        cache.set(
            MARKET_HUB_SUMMARIES_CACHE_KEY,
            summaries,
            settings.MARKET_SYNC_CACHE_SECONDS,
        )
    return summaries


def _pagination_extra_query(request, *, exclude=("page",)):
    query = request.GET.copy()
    for key in exclude:
        query.pop(key, None)
    return query.urlencode()


def market_hub(request):
    """Category landing page — browse markets by topic (Politics, Sports, Crypto, etc.)."""
    search = request.GET.get("q", "").strip()
    source = normalize_source_filter(request.GET.get("source", ""))
    source_filter_urls = build_source_filter_urls(
        base_url=reverse("markets:list"),
        active_source=source,
        extra={"q": search},
    )
    search_results = []
    if search:
        search_results = attach_user_forecasts_to_markets(
            request.user,
            get_markets_for_display(
                status=Market.Status.OPEN,
                search=search,
                source=source or None,
            ),
        )
    return render(
        request,
        "markets/market_hub.html",
        {
            "category_summaries": _load_market_hub_summaries(),
            "active_source": source,
            "source_filter_urls": source_filter_urls,
            "search_query": search,
            "search_results": search_results,
            "clear_search_url": build_browse_clear_search_url(
                base_url=reverse("markets:list"),
                source=source,
            ),
        },
    )


def market_list(request):
    status = request.GET.get("status", "")
    category = normalize_category_filter(request.GET.get("category", ""))
    search = request.GET.get("q", "")
    source = normalize_source_filter(request.GET.get("source", ""))
    sort = normalize_sort_filter(request.GET.get("sort", ""))
    ending = normalize_ending_filter(request.GET.get("ending", ""))
    ending_hours = ending_window_hours(ending)

    # The ending-soon window operates on open markets only.
    effective_status = Market.Status.OPEN if ending else status

    qs = get_markets_list(
        status=effective_status or None,
        category=category or None,
        search=search or None,
        source=source or None,
        ending_within_hours=ending_hours,
    )
    page_size = settings.MARKET_LIST_PAGE_SIZE

    qs = apply_markets_list_ordering(
        qs,
        sort=sort,
        ending_within_hours=ending_hours,
    )
    paginator = Paginator(qs, page_size)

    page_obj = paginator.get_page(request.GET.get("page"))
    markets = attach_user_forecasts_to_markets(request.user, list(page_obj.object_list))

    source_filter_urls = build_source_filter_urls(
        base_url=reverse("markets:all"),
        active_source=source,
        extra={"q": search, "status": status, "category": category, "sort": sort, "ending": ending},
    )
    clear_category_params = {
        key: value
        for key, value in {
            "q": search,
            "status": status,
            "source": source,
            "sort": sort,
            "ending": ending,
        }.items()
        if value
    }
    clear_category_query = urlencode(clear_category_params)
    clear_category_url = (
        f"{reverse('markets:all')}?{clear_category_query}"
        if clear_category_query
        else reverse("markets:all")
    )
    return render(
        request,
        "markets/market_list.html",
        {
            "markets": markets,
            "market_count": paginator.count,
            "page_obj": page_obj,
            "pagination_query": _pagination_extra_query(request),
            "categories": get_market_categories(),
            "current_status": status,
            "current_category": category,
            "current_category_label": (
                get_category_for_slug(category).name if category else ""
            ),
            "current_source": source,
            "current_sort": sort,
            "current_ending": ending,
            "clear_category_url": clear_category_url,
            "ending_choices": ENDING_WINDOW_CHOICES,
            "sort_choices": MARKET_SORT_CHOICES,
            "search_query": search,
            "source_filter_urls": source_filter_urls,
        },
    )


def market_detail(request, slug):
    market = get_object_or_404(Market, slug=slug)

    from markets.composite_redirect import get_composite_redirect_market

    composite_market = get_composite_redirect_market(market)
    if composite_market:
        target = reverse("markets:detail", kwargs={"slug": composite_market.slug})
        query_string = request.META.get("QUERY_STRING", "")
        if query_string:
            target = f"{target}?{query_string}"
        return redirect(target, permanent=True)

    enqueue_market_refresh_if_stale(market)

    predictions = get_market_predictions(market)
    discussions = get_market_prediction_discussions(market=market, predictions=predictions)
    all_comment_ids = []
    for threads in discussions.values():
        all_comment_ids.extend(collect_comment_ids(threads))
    comment_votes = get_user_comment_votes(request.user, all_comment_ids)
    comment_vote_summaries = get_vote_summaries_for_targets(
        target_type=Vote.TargetType.COMMENT,
        target_ids=all_comment_ids,
    )
    for threads in discussions.values():
        attach_comment_votes(threads, comment_votes)
        attach_vote_summaries_to_comments(threads, comment_vote_summaries)
    prediction_votes = get_user_prediction_votes(request.user, [p.id for p in predictions])
    prediction_vote_previews = get_vote_previews_for_targets(
        target_type=Vote.TargetType.PREDICTION,
        target_ids=[p.id for p in predictions],
    )
    bookmarked_ids = get_user_bookmarked_ids(
        request.user,
        Bookmark.TargetType.PREDICTION,
        [p.id for p in predictions],
    )

    existing_forecast = None
    forecast_form = None
    active_challenges = []
    creator_program_enabled = False
    if request.user.is_authenticated:
        from accounts.monetization_selectors import get_creator_program_or_none

        program = get_creator_program_or_none(request.user)
        creator_program_enabled = program is not None and program.is_enabled
        if market.is_forecastable:
            existing_forecast = get_user_active_prediction(request.user, market)
            active_challenges = get_active_challenge_contexts_for_market(
                user=request.user,
                market=market,
            )

    if market.is_forecastable and not existing_forecast:
        forecast_form = ForecastForm(
            market=market,
            creator_program_enabled=creator_program_enabled,
        )

    prediction_sections = [
        {
            "prediction": p,
            "threads": discussions.get(p.id, []),
            "comment_count": len(collect_comment_ids(discussions.get(p.id, []))),
            "prediction_vote": prediction_votes.get(p.id, 0),
            "is_bookmarked": p.id in bookmarked_ids,
            "reputation_stakes": calculate_reputation_stakes(
                predicted_outcome=p.predicted_outcome,
                probability_snapshot=p.probability_at_prediction_time,
                predicted_direction=p.predicted_direction,
            ),
            "like_preview": prediction_vote_previews.get(p.id, {}).get("likes", []),
            "dislike_preview": prediction_vote_previews.get(p.id, {}).get("dislikes", []),
        }
        for p in predictions
    ]

    from accounts.follow_selectors import is_watching_market
    from markets.navigation import resolve_market_return_url

    return_url = resolve_market_return_url(request, slug=slug)

    return render(
        request,
        "markets/market_detail.html",
        {
            "market": market,
            "predictions": predictions,
            "prediction_sections": prediction_sections,
            "polymarket_embed": build_polymarket_embed_context(market),
            "forecast_form": forecast_form,
            "existing_forecast": existing_forecast,
            "active_challenges": active_challenges,
            "creator_program_enabled": creator_program_enabled,
            "is_watching_market": is_watching_market(user=request.user, market=market),
            "return_url": return_url,
            "forecast_posted": request.GET.get("posted") == "1",
        },
    )
