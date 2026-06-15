"""Bearer token authentication for REST API v1.

Reuses ``McpToken`` credentials — tokens minted at ``/mcp/tokens/`` work for
both MCP and REST. Session authentication remains available for browser clients.
"""

from rest_framework.authentication import BaseAuthentication, SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed

from mcp.auth import extract_bearer_token
from mcp.tokens import resolve_token


class McpBearerAuthentication(BaseAuthentication):
    """Authenticate via ``Authorization: Bearer mcp_…`` token."""

    www_authenticate_header = "Bearer"

    def authenticate(self, request):
        raw = extract_bearer_token(request)
        if not raw:
            return None
        token = resolve_token(raw)
        if token is None:
            raise AuthenticationFailed("Invalid or expired API token.")
        request.api_token = token
        return (token.user, token)

    def authenticate_header(self, request):
        return self.www_authenticate_header


class ApiSessionAuthentication(SessionAuthentication):
    """Session auth that skips CSRF enforcement for programmatic JSON clients."""

    def enforce_csrf(self, request):
        return
