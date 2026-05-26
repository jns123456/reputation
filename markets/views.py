from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from accounts.bookmark_selectors import get_user_bookmarked_ids
from accounts.models import Bookmark
from comments.selectors import (
    attach_comment_votes,
    collect_comment_ids,
    get_market_prediction_discussions,
    get_user_comment_votes,
    get_user_prediction_votes,
)
from integrations.kalshi.embed import build_kalshi_embed_context
from integrations.polymarket.embed import build_polymarket_embed_context
from integrations.sync import refresh_market
from markets.models import Market
from markets.selectors import get_market_categories, get_markets_for_display
from markets.sort_options import MARKET_SORT_CHOICES, normalize_sort_filter
from markets.source_filters import build_source_filter_urls, kalshi_enabled, normalize_source_filter
from predictions.forms import ForecastForm
from predictions.selectors import get_market_predictions, get_user_active_prediction
from reputation.services import calculate_reputation_stakes


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
        base_url=reverse("markets:list"),
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
    market = refresh_market(market)

    predictions = get_market_predictions(market)
    discussions = get_market_prediction_discussions(market=market, predictions=predictions)
    all_comment_ids = []
    for threads in discussions.values():
        all_comment_ids.extend(collect_comment_ids(threads))
    comment_votes = get_user_comment_votes(request.user, all_comment_ids)
    for threads in discussions.values():
        attach_comment_votes(threads, comment_votes)
    prediction_votes = get_user_prediction_votes(request.user, [p.id for p in predictions])
    bookmarked_ids = get_user_bookmarked_ids(
        request.user,
        Bookmark.TargetType.PREDICTION,
        [p.id for p in predictions],
    )

    existing_forecast = None
    forecast_form = None
    if request.user.is_authenticated and market.is_open:
        existing_forecast = get_user_active_prediction(request.user, market)
        forecast_form = (
            ForecastForm(market=market) if not existing_forecast else None
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
            ),
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
        },
    )
