from django.conf import settings
from django.core.cache import cache
from django.shortcuts import get_object_or_404, render
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
from integrations.kalshi.embed import build_kalshi_embed_context
from integrations.polymarket.embed import build_polymarket_embed_context
from integrations.celery_utils import enqueue_market_refresh_if_stale
from markets.models import Market
from markets.selectors import get_market_categories, get_market_hub_category_summaries, get_markets_for_display
from markets.sort_options import MARKET_SORT_CHOICES, normalize_sort_filter
from markets.source_filters import build_browse_clear_search_url, build_source_filter_urls, kalshi_enabled, normalize_source_filter
from predictions.forms import ForecastForm
from predictions.selectors import get_market_predictions, get_user_active_prediction
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
        search_results = get_markets_for_display(
            status=Market.Status.OPEN,
            search=search,
            source=source or None,
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
    category = request.GET.get("category", "")
    search = request.GET.get("q", "")
    source = normalize_source_filter(request.GET.get("source", ""))
    sort = normalize_sort_filter(request.GET.get("sort", ""))

    markets = get_markets_for_display(
        status=status or None,
        category=category or None,
        search=search or None,
        source=source or None,
        sort=sort or None,
    )
    source_filter_urls = build_source_filter_urls(
        base_url=reverse("markets:all"),
        active_source=source,
        extra={"q": search, "status": status, "category": category, "sort": sort},
    )
    return render(
        request,
        "markets/market_list.html",
        {
            "markets": markets,
            "categories": get_market_categories(),
            "current_status": status,
            "current_category": category,
            "current_source": source,
            "current_sort": sort,
            "sort_choices": MARKET_SORT_CHOICES,
            "search_query": search,
            "source_filter_urls": source_filter_urls,
        },
    )


def market_detail(request, slug):
    market = get_object_or_404(Market, slug=slug)
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
    if request.user.is_authenticated and market.is_open:
        existing_forecast = get_user_active_prediction(request.user, market)
        forecast_form = (
            ForecastForm(market=market) if not existing_forecast else None
        )
        active_challenges = get_active_challenge_contexts_for_market(
            user=request.user,
            market=market,
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

    return render(
        request,
        "markets/market_detail.html",
        {
            "market": market,
            "predictions": predictions,
            "prediction_sections": prediction_sections,
            "polymarket_embed": build_polymarket_embed_context(market),
            "kalshi_embed": build_kalshi_embed_context(market) if kalshi_enabled() else None,
            "forecast_form": forecast_form,
            "existing_forecast": existing_forecast,
            "active_challenges": active_challenges,
        },
    )
