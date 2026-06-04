from django import template

from accounts.models import SubscriberAudience
from accounts.monetization_services import can_view_audience_content

register = template.Library()


@register.filter
def can_view_creator_content(content, viewer):
    """Usage: ``{{ post|can_view_creator_content:user }}`` — Prediction or Post with ``user`` and ``audience``."""
    creator = content.user
    return can_view_audience_content(
        viewer=viewer,
        creator=creator,
        audience=content.audience,
    )


@register.filter
def is_subscriber_only(content):
    return getattr(content, "audience", None) == SubscriberAudience.SUBSCRIBERS


@register.filter
def creator_program_enabled(user):
    program = getattr(user, "creator_program", None)
    return program is not None and program.is_enabled


@register.filter
def is_subscribed_to(viewer, creator):
    from accounts.monetization_services import is_active_subscriber

    return is_active_subscriber(viewer=viewer, creator=creator)
