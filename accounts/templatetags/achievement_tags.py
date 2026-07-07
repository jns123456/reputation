from django import template

from accounts.achievement_services import is_founding_forecaster

register = template.Library()


@register.filter
def is_founding_forecaster_user(user):
    return is_founding_forecaster(user)
