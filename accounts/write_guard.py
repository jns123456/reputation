"""Unified write-path anti-abuse gate (AGENTS.md §16).

Every user-facing write service (forecasts, comments, votes, forum posts, follows)
calls ``guard_write_action`` before persisting. MCP write tools use the same domain
services, so rate limits and spam checks apply equally on web and agent paths.
"""

from django.conf import settings
from django.utils.translation import gettext_lazy as _

from accounts import abuse_services


class ContentRejected(Exception):
    """Raised when submitted text fails anti-spam assessment."""

    def __init__(self, message=None, *, reasons=None):
        self.reasons = list(reasons or [])
        super().__init__(message or _("Content rejected by anti-spam checks."))


def write_guard_enabled():
    return getattr(settings, "ABUSE_WRITE_GUARD_ENABLED", True)


def guard_write_action(*, action, user, text=None, content_scope=None):
    """Rate-limit and optionally assess text before a write action proceeds."""
    if not write_guard_enabled():
        return

    if user is None or not getattr(user, "is_authenticated", False):
        return

    abuse_services.enforce_rate_limit(action=action, user=user)

    normalized = (text or "").strip()
    if not normalized:
        return

    scope = content_scope or f"write:{action}"
    assessment = abuse_services.assess_content(user=user, text=normalized, scope=scope)
    if assessment["is_spam"]:
        raise ContentRejected(reasons=assessment["reasons"])


def write_guard_user_message(exc):
    """Map write-guard exceptions to a safe user-facing string."""
    if isinstance(exc, abuse_services.RateLimitExceeded):
        return _("You're doing that too often. Please wait a bit and try again.")
    if isinstance(exc, ContentRejected):
        return str(exc)
    return str(exc)
