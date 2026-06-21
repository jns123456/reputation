from django import template

from predictions.share_copy import get_forecast_share_copy

register = template.Library()


@register.inclusion_tag(
    "predictions/partials/forecast_share_button.html",
    takes_context=True,
)
def forecast_share_button(
    context,
    prediction,
    extra_class="",
    label=None,
    icon="share-2",
    icon_class="h-4 w-4 shrink-0",
    icon_only=False,
    button_id="",
):
    request = context["request"]
    share_copy = get_forecast_share_copy(prediction)
    if label is None and not icon_only:
        label = share_copy["button_label"]
    return {
        "request": request,
        "prediction": prediction,
        "share_copy": share_copy,
        "extra_class": extra_class,
        "label": label,
        "icon": icon,
        "icon_class": icon_class,
        "icon_only": icon_only,
        "button_id": button_id,
    }
