"""MCP HTTP endpoint (AGENTS.md §17).

A minimal JSON-RPC 2.0 surface exposing MCP methods over HTTP POST. Method
routing is shared with the stdio transport via ``mcp.rpc`` so both behave
identically. A GET request returns the public discovery document.

Token auth only (no session) → CSRF-exempt. Read tools are always on; write
tools are gated by feature flags and scopes inside ``services.execute_tool``.
"""

import json

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from accounts import abuse_services
from accounts.http_utils import enforce_ip_rate_limit
from mcp.auth import authenticate_request
from mcp.errors import McpError
from mcp.rpc import PUBLIC_METHODS, discovery_document, handle_method


def _rpc_error(request_id, code, message, http_status=400):
    return JsonResponse(
        {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}},
        status=http_status,
    )


def _rpc_result(request_id, result):
    return JsonResponse({"jsonrpc": "2.0", "id": request_id, "result": result})


@csrf_exempt
@require_http_methods(["GET", "POST"])
def mcp_endpoint(request):
    if not getattr(settings, "MCP_ENABLED", True):
        return JsonResponse({"error": "MCP is disabled."}, status=404)

    if request.method == "GET":
        return JsonResponse(discovery_document())

    try:
        enforce_ip_rate_limit(request=request, action="mcp_http")
    except abuse_services.RateLimitExceeded:
        return _rpc_error(
            None, "rate_limited", "Too many MCP requests.", http_status=429
        )

    try:
        payload = json.loads(request.body or b"{}")
    except (json.JSONDecodeError, ValueError):
        return _rpc_error(None, "parse_error", "Invalid JSON body.")

    request_id = payload.get("id")
    method = payload.get("method")
    params = payload.get("params") or {}

    token = None
    if method not in PUBLIC_METHODS:
        token = authenticate_request(request)
        if token is None:
            return _rpc_error(
                request_id, "unauthenticated", "Missing or invalid MCP token.", http_status=401
            )

    try:
        result = handle_method(token=token, method=method, params=params)
    except McpError as exc:
        return _rpc_error(request_id, exc.code, exc.message, http_status=exc.http_status)
    except PermissionError as exc:
        return _rpc_error(request_id, "unauthenticated", str(exc), http_status=401)

    return _rpc_result(request_id, result)
