from django import template
import json

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
    )


@register.filter
def prediction_reputation_delta(prediction):
    """Actual reputation change when resolved; None if still pending."""
    if prediction.status != prediction.Status.RESOLVED or prediction.is_correct is None:
        return None
    from reputation.services import calculate_reputation_delta

    return calculate_reputation_delta(
        is_correct=prediction.is_correct,
        predicted_outcome=prediction.predicted_outcome,
        probability_snapshot=prediction.probability_at_prediction_time,
    )


@register.filter
def market_source_label(market):
    source = getattr(market, "source", "")
    if source == "kalshi":
        return "Kalshi"
    if source == "polymarket":
        return "Polymarket"
    return "Market"


@register.simple_tag
def outcome_stakes(market, outcome_label):
    from reputation.services import calculate_reputation_stakes

    return calculate_reputation_stakes(
        predicted_outcome=outcome_label,
        probability_snapshot=market.current_probability or {},
    )
