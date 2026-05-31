"""Shared MCP JSON-RPC method dispatch (AGENTS.md §17).

Single source of truth for method routing so every transport — the HTTP endpoint
(``mcp.views``) and the stdio server (``mcp.transport``) — behaves identically and
delegates to the same ``mcp.services`` layer.
"""

from django.conf import settings

from mcp.prompts import PROMPT_CATALOG, get_prompt
from mcp.registry import tool_catalog
from mcp.resources import RESOURCE_CATALOG
from mcp.services import McpContext, execute_tool, new_request_id, read_resource

# Methods that do not require authentication.
PUBLIC_METHODS = {"initialize", "server/info"}


def discovery_document():
    return {
        "name": "predictstamp-mcp",
        "version": "1.0",
        "instructions": (
            "Authenticate with a bearer MCP token. Read tools are available to "
            "token holders; write tools require scopes, trust, and feature flags."
        ),
        "capabilities": {"tools": True, "resources": True, "prompts": True},
        "writes_enabled": bool(getattr(settings, "MCP_WRITES_ENABLED", False)),
        "tools": tool_catalog(),
        "resources": RESOURCE_CATALOG,
        "prompts": [
            {"name": name, "description": meta["description"]}
            for name, meta in PROMPT_CATALOG.items()
        ],
    }


def handle_method(*, token, method, params=None):
    """Dispatch one MCP method. ``token`` may be None only for PUBLIC_METHODS.

    Returns the JSON-RPC ``result`` payload. Raises ``McpError`` on failure and
    ``PermissionError`` when a token is required but missing.
    """
    params = params or {}

    if method in PUBLIC_METHODS:
        return discovery_document()

    if token is None:
        raise PermissionError("Missing or invalid MCP token.")

    if method == "tools/list":
        return {"tools": tool_catalog()}
    if method == "resources/list":
        return {"resources": RESOURCE_CATALOG}
    if method == "prompts/list":
        return {
            "prompts": [
                {"name": n, "description": m["description"]}
                for n, m in PROMPT_CATALOG.items()
            ]
        }
    if method == "prompts/get":
        return get_prompt(params.get("name"))

    context = McpContext(
        user=token.user,
        token=token,
        dry_run=bool(params.get("dry_run", False)),
        request_id=new_request_id(),
    )
    if method == "tools/call":
        return execute_tool(
            context=context,
            tool_name=params.get("name"),
            arguments=params.get("arguments") or {},
        )
    if method == "resources/read":
        return {"contents": read_resource(context=context, uri=params.get("uri"))}

    from mcp.errors import McpError

    raise McpError("unknown_method", f"Unknown method: {method}", http_status=404)
