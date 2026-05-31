"""MCP request authentication (AGENTS.md §17).

Every MCP request must present a valid bearer token (no unauthenticated writes,
ever). Read access also requires a token in this implementation — there is no
anonymous MCP surface by default.
"""

from mcp.tokens import resolve_token


def extract_bearer_token(request):
    header = request.META.get("HTTP_AUTHORIZATION", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


def authenticate_request(request):
    """Return a valid McpToken for the request, or None."""
    raw = extract_bearer_token(request)
    return resolve_token(raw)
