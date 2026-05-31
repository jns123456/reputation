"""MCP token creation and verification (AGENTS.md §17).

Raw tokens are never stored — only their SHA-256 hash. The raw value is returned
exactly once at creation time and must be surfaced to the operator immediately.
"""

import hashlib
import secrets

from django.utils import timezone

from mcp.models import McpToken

TOKEN_PREFIX = "mcp"


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _generate_raw():
    prefix = secrets.token_hex(4)  # 8 chars, non-secret identifier
    secret = secrets.token_urlsafe(32)
    raw = f"{TOKEN_PREFIX}_{prefix}_{secret}"
    return prefix, raw


def create_token(*, user, name, scopes=None, rate_limit_tier=None, expires_at=None):
    """Create an McpToken and return (token, raw_value). Raw is shown only once."""
    from accounts.agent_services import account_allowed_scopes

    prefix, raw = _generate_raw()
    if scopes is None:
        # Default to what the account is allowed today (read-only for new agents).
        scopes = account_allowed_scopes(user)
    if rate_limit_tier is None:
        agent_profile = getattr(user, "agent_profile", None)
        rate_limit_tier = (
            agent_profile.rate_limit_tier if agent_profile is not None else "new"
        )
    token = McpToken.objects.create(
        user=user,
        name=name,
        prefix=prefix,
        token_hash=hash_token(raw),
        scopes=list(scopes),
        rate_limit_tier=rate_limit_tier,
        expires_at=expires_at,
    )
    return token, raw


def resolve_token(raw_token: str):
    """Return a valid McpToken for the raw value, or None.

    Updates ``last_used_at`` on success. Invalid/expired/revoked tokens return
    None so callers treat them as unauthenticated.
    """
    if not raw_token:
        return None
    token = McpToken.objects.filter(token_hash=hash_token(raw_token)).select_related(
        "user", "user__agent_profile"
    ).first()
    if token is None or not token.is_valid:
        return None
    token.last_used_at = timezone.now()
    token.save(update_fields=["last_used_at"])
    return token


def rotate_token(token: McpToken):
    """Revoke ``token`` and issue a replacement with the same scopes/tier."""
    token.revoke()
    return create_token(
        user=token.user,
        name=f"{token.name} (rotated)",
        scopes=token.scopes,
        rate_limit_tier=token.rate_limit_tier,
        expires_at=token.expires_at,
    )
