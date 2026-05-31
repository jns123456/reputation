"""Read queries for MCP models."""

from mcp.models import McpToken, McpToolCallLog


def get_user_tokens(user, *, include_revoked=True):
    qs = McpToken.objects.filter(user=user)
    if not include_revoked:
        qs = qs.filter(is_active=True, revoked_at__isnull=True)
    return qs.order_by("-created_at")


def get_recent_token_calls(token, *, limit=20):
    return McpToolCallLog.objects.filter(token=token).order_by("-created_at")[:limit]
