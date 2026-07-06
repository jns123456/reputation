"""Audit F1 and multi-binary mis-scores — run via manage.py shell or Heroku one-off."""
from django.db.models import Count, Q

from integrations.polymarket.client import (
    grouped_event_all_submarkets_resolved,
    grouped_submarket_resolved_yes,
)
from markets.forecast_modes import ForecastMode, get_forecast_mode
from markets.models import Market
from predictions.models import Prediction
from predictions.services import prediction_is_correct_for_resolved_market


def f1_market_queryset():
    return Market.objects.filter(
        Q(polymarket_slug__icontains="f1")
        | Q(polymarket_slug__icontains="grand-prix")
        | Q(title__icontains="Grand Prix")
        | Q(browse_area_slugs__contains=["formula-1"])
    ).distinct()


def audit(*, refresh_stale=False, limit_refresh=20):
    from integrations.services import refresh_market_from_polymarket

    print("=== F1 MARKETS SUMMARY ===")
    f1_markets = f1_market_queryset()
    print("total_markets", f1_markets.count())
    for row in f1_markets.values("status").annotate(c=Count("id")).order_by("status"):
        print(" status", row["status"], row["c"])

    resolved_multi = [
        m
        for m in f1_markets.filter(status=Market.Status.RESOLVED).iterator()
        if get_forecast_mode(m) == ForecastMode.MULTI_BINARY
    ]
    print("resolved_multi_binary", len(resolved_multi))

    f1_issues = []
    f1_preds = 0
    stale_markets = []

    for market in resolved_multi:
        pred_count = Prediction.objects.filter(
            market=market, status=Prediction.Status.RESOLVED
        ).count()
        winner = (market.resolved_outcome or "")[:50]
        slug = market.polymarket_slug or market.slug
        print(f"  {slug} | preds={pred_count} | display_winner={winner}")

        event = market.polymarket_event_raw or {}
        all_resolved = grouped_event_all_submarkets_resolved(event) if event.get("markets") else False
        if not all_resolved and event.get("markets"):
            stale_markets.append(slug)

        for prediction in Prediction.objects.filter(
            market=market, status=Prediction.Status.RESOLVED
        ).select_related("user"):
            f1_preds += 1
            expected = prediction_is_correct_for_resolved_market(market, prediction)
            if expected is None:
                f1_issues.append(
                    {
                        "type": "indeterminate",
                        "market": slug,
                        "user": prediction.user.username,
                        "pick": prediction.predicted_outcome,
                        "dir": prediction.predicted_direction,
                        "is_correct": prediction.is_correct,
                        "id": prediction.id,
                    }
                )
            elif prediction.is_correct != expected:
                f1_issues.append(
                    {
                        "type": "wrong",
                        "market": slug,
                        "user": prediction.user.username,
                        "pick": prediction.predicted_outcome,
                        "dir": prediction.predicted_direction,
                        "is_correct": prediction.is_correct,
                        "expected": expected,
                        "id": prediction.id,
                    }
                )

    print("\n=== F1 RESOLVED MULTI-BINARY AUDIT ===")
    print("predictions_checked", f1_preds)
    print("issues_found", len(f1_issues))
    print("stale_event_raw_markets", len(stale_markets))
    for slug in stale_markets[:15]:
        print("  stale:", slug)
    for row in f1_issues:
        print(row)

    # Podium / multi-yes pattern markets across F1
    print("\n=== F1 MULTI-YES MARKET SHAPE ===")
    for market in resolved_multi:
        event = market.polymarket_event_raw or {}
        yes_count = 0
        for raw in event.get("markets") or []:
            label = str(raw.get("groupItemTitle") or "").strip()
            if not label:
                continue
            sub = grouped_submarket_resolved_yes(event, label)
            if sub is True:
                yes_count += 1
        if yes_count > 1:
            print(
                f"  MULTI_YES slug={market.polymarket_slug} yes_buckets={yes_count} "
                f"display_winner={market.resolved_outcome}"
            )

    if refresh_stale and stale_markets:
        print(f"\n=== REFRESHING UP TO {limit_refresh} STALE F1 MARKETS ===")
        refreshed = 0
        for market in resolved_multi[:limit_refresh]:
            if (market.polymarket_slug or "") not in stale_markets:
                continue
            refresh_market_from_polymarket(market)
            refreshed += 1
            print("  refreshed", market.polymarket_slug)
        print("refreshed_count", refreshed)

    return {
        "f1_markets": f1_markets.count(),
        "resolved_multi_binary": len(resolved_multi),
        "f1_predictions_checked": f1_preds,
        "f1_issues": f1_issues,
        "stale_markets": stale_markets,
    }


if __name__ == "__main__":
    audit()
