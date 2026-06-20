"""@mention autocomplete — suggest users the actor follows."""

import re

_MENTION_PREFIX_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.\-]{0,149}$")


def normalize_mention_prefix(prefix: str) -> str:
    """Strip a leading ``@`` and return a safe username prefix fragment."""
    cleaned = (prefix or "").strip()
    if cleaned.startswith("@"):
        cleaned = cleaned[1:]
    if not cleaned:
        return ""
    if _MENTION_PREFIX_RE.match(cleaned):
        return cleaned
    # Drop invalid trailing chars while the user is still typing.
    return re.sub(r"[^\w.\-]", "", cleaned, flags=re.ASCII)[:150]


def search_following_for_mention(*, user, prefix="", limit=8):
    """Return up to ``limit`` followed users whose username starts with ``prefix``."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    if not user or not user.is_authenticated:
        return User.objects.none()

    cleaned = normalize_mention_prefix(prefix)
    qs = (
        User.objects.filter(is_active=True, follower_relations__follower=user)
        .select_related("profile")
        .exclude(pk=user.pk)
        .order_by("-follower_relations__created_at")
        .distinct()
    )
    if cleaned:
        qs = qs.filter(username__istartswith=cleaned)
    return qs[:limit]
