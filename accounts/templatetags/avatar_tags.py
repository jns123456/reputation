from django import template

from accounts.avatar_services import generated_avatar_url

register = template.Library()


@register.simple_tag
def user_avatar_url(user, size=None):
    if user is None:
        return ""
    parsed_size = int(size) if size else None
    return generated_avatar_url(user, size=parsed_size)
