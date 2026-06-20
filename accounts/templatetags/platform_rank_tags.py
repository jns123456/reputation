from django import template

from reputation.platform_rank import get_user_platform_top_rank_badges

register = template.Library()


@register.inclusion_tag("accounts/partials/profile_rank_badges.html")
def platform_rank_badges_for(user, compact=None):
    return {
        "platform_rank_badges": get_user_platform_top_rank_badges(user),
        "compact": compact or "",
    }
