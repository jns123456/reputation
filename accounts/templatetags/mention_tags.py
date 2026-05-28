"""Template filter that renders @mentions as profile links — XSS-safe.

The input text is fully HTML-escaped *first*, then only @username tokens that
match an existing user are wrapped in anchors. User-controlled content can never
inject markup because escaping happens before any tag is added.
"""

from django import template
from django.urls import reverse
from django.utils.html import escape, linebreaks
from django.utils.safestring import mark_safe

from accounts.mention_services import _MENTION_RE, extract_mention_usernames

register = template.Library()


@register.filter(is_safe=True, needs_autoescape=False)
def linkify_mentions(text):
    """Escape ``text`` and turn @mentions of real users into profile links."""
    if not text:
        return ""

    escaped = escape(text)
    usernames = extract_mention_usernames(text)
    if not usernames:
        return mark_safe(escaped)

    from accounts.models import User

    existing = set(
        User.objects.filter(username__in=usernames).values_list("username", flat=True)
    )
    if not existing:
        return mark_safe(escaped)

    def _replace(match):
        token = match.group(0)  # e.g. "@alice" (may include trailing . or -)
        username = match.group(1).rstrip(".-")
        if username not in existing:
            return token
        url = reverse("accounts:profile", kwargs={"username": username})
        trailing = token[1 + len(username):]
        return f'<a href="{url}" class="pr-mention">@{username}</a>{trailing}'

    return mark_safe(_MENTION_RE.sub(_replace, escaped))


@register.filter(is_safe=True, needs_autoescape=False)
def linkify_mentions_br(text):
    """Like ``linkify_mentions`` but also converts newlines to <br>/<p>."""
    if not text:
        return ""
    linked = linkify_mentions(text)
    return mark_safe(linebreaks(linked))
