from zoneinfo import ZoneInfo

from django import template
from django.conf import settings
from django.utils.formats import date_format

from accounts.client_timezone import timezone_display_label

register = template.Library()


def _client_timezone_name(context) -> str:
    request = context.get("request")
    if request is not None:
        tz_name = getattr(request, "client_timezone_name", None)
        if tz_name:
            return tz_name
    return settings.TIME_ZONE


@register.simple_tag(takes_context=True)
def local_kickoff_time(context, value, fmt="M j · H:i"):
    """Format a sports kickoff in the visitor timezone (IP/CDN), not site-wide UTC."""
    if not value:
        return ""
    tz_name = _client_timezone_name(context)
    localized = value.astimezone(ZoneInfo(tz_name))
    formatted = date_format(localized, fmt)
    request = context.get("request")
    label = getattr(request, "client_timezone_label", None) if request else None
    if not label:
        label = timezone_display_label(tz_name, localized)
    return f"{formatted} {label}"
