"""Deterministic profile avatars — no uploads or object storage required."""

from urllib.parse import urlencode

from django.conf import settings


def avatar_seed(user) -> str:
    """Stable seed for generated avatars (survives username/display name changes)."""
    return str(user.pk)


def generated_avatar_url(user, *, size: int | None = None) -> str:
    """Public DiceBear PNG URL unique per user account."""
    style = getattr(settings, "AVATAR_DICEBEAR_STYLE", "identicon")
    base = getattr(settings, "AVATAR_DICEBEAR_BASE_URL", "https://api.dicebear.com/9.x").rstrip("/")
    params = {"seed": avatar_seed(user)}
    if size is not None:
        params["size"] = str(size)
    return f"{base}/{style}/png?{urlencode(params)}"
