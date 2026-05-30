import json

from django import template
from django.utils.translation import gettext as _

register = template.Library()


@register.filter
def as_percent(value):
    try:
        v = float(value)
        if v <= 1:
            v *= 100
        return f"{v:.0f}"
    except (TypeError, ValueError):
        return value


@register.filter
def pretty_json(value):
    if not value:
        return ""
    try:
        return json.dumps(value, indent=2, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


@register.filter
def prediction_discussion_id(prediction):
    return f"prediction-discussion-{prediction.pk}"


@register.filter
def prediction_stakes(prediction):
    from reputation.services import calculate_reputation_stakes

    return calculate_reputation_stakes(
        predicted_outcome=prediction.predicted_outcome,
        probability_snapshot=prediction.probability_at_prediction_time,
        predicted_direction=prediction.predicted_direction,
    )


@register.filter
def prediction_reputation_delta(prediction):
    """Actual reputation change once resolved or exited; None if still pending."""
    if prediction.status == prediction.Status.EXITED:
        event = prediction.reputation_events.filter(
            event_type="exited_prediction"
        ).first()
        if event:
            return event.points_delta
        if prediction.probability_at_exit_time:
            from reputation.services import calculate_exit_reputation_delta

            return calculate_exit_reputation_delta(
                predicted_outcome=prediction.predicted_outcome,
                entry_probability_snapshot=prediction.probability_at_prediction_time,
                exit_probability_snapshot=prediction.probability_at_exit_time,
                predicted_direction=prediction.predicted_direction,
            )
        return None

    if prediction.status != prediction.Status.RESOLVED or prediction.is_correct is None:
        return None
    from reputation.services import calculate_reputation_delta

    return calculate_reputation_delta(
        is_correct=prediction.is_correct,
        predicted_outcome=prediction.predicted_outcome,
        probability_snapshot=prediction.probability_at_prediction_time,
        predicted_direction=prediction.predicted_direction,
    )


@register.filter
def live_reputation_pnl(prediction):
    """Live mark-to-market reputation P&L for an open forecast; None otherwise."""
    from reputation.services import calculate_unrealized_reputation

    return calculate_unrealized_reputation(prediction)


@register.simple_tag
def exit_reputation_preview(prediction, market):
    from reputation.services import calculate_exit_reputation_delta

    return calculate_exit_reputation_delta(
        predicted_outcome=prediction.predicted_outcome,
        entry_probability_snapshot=prediction.probability_at_prediction_time,
        exit_probability_snapshot=getattr(market, "current_probability", {}) or {},
        predicted_direction=prediction.predicted_direction,
    )


@register.filter
def localized_outcome(value):
    from markets.localization import localize_outcome_label

    return localize_outcome_label(str(value or ""))


@register.filter
def market_source_label(market):
    source = getattr(market, "source", "")
    if source == "polymarket":
        return _("Polymarket")
    return _("Market")


def _sorted_probability_items(market):
    probability = getattr(market, "current_probability", None) or {}
    items = []
    for label, value in probability.items():
        try:
            prob = float(value)
        except (TypeError, ValueError):
            continue
        if prob > 1:
            prob = prob / 100
        prob = max(0.0, min(1.0, prob))
        items.append(
            {
                "label": label,
                "probability": prob,
                "prob_percent": int(round(prob * 100)),
                "no_percent": int(round((1 - prob) * 100)),
            }
        )
    return sorted(items, key=lambda item: item["probability"], reverse=True)


@register.filter
def probability_items_sorted(market):
    """Outcomes sorted by highest current probability first."""
    return _sorted_probability_items(market)


@register.filter
def top_probability_items(market, limit=2):
    """Top N outcomes for compact multi-outcome cards."""
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 2
    return _sorted_probability_items(market)[:limit]


@register.filter
def remaining_probability_count(market, shown=2):
    try:
        shown = int(shown)
    except (TypeError, ValueError):
        shown = 2
    return max(0, len(_sorted_probability_items(market)) - shown)


@register.filter
def is_multi_outcome_market(market):
    return len(getattr(market, "outcome_labels", []) or []) > 2


@register.simple_tag
def outcome_stakes(market, outcome_label, predicted_direction="yes"):
    from reputation.services import calculate_reputation_stakes

    return calculate_reputation_stakes(
        predicted_outcome=outcome_label,
        probability_snapshot=market.current_probability or {},
        predicted_direction=predicted_direction,
    )
