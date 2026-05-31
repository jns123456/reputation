"""Stdio MCP transport (AGENTS.md §17).

A real, dependency-free MCP server speaking newline-delimited JSON-RPC 2.0 over
stdin/stdout. It authenticates once with a bearer token and then dispatches every
request through the shared ``mcp.rpc`` layer — so it enforces the exact same
scopes, trust, rate limits, circuit breakers, dry-run, and audit logging as the
HTTP endpoint. This is the binding an external MCP client (e.g. an LLM host) can
launch as a subprocess.
"""

import json
import sys

from mcp.errors import McpError
from mcp.rpc import PUBLIC_METHODS, handle_method
from mcp.tokens import resolve_token


class StdioMcpServer:
    def __init__(self, *, raw_token="", stdin=None, stdout=None):
        self.token = resolve_token(raw_token) if raw_token else None
        self.stdin = stdin or sys.stdin
        self.stdout = stdout or sys.stdout

    def _write(self, message):
        self.stdout.write(json.dumps(message) + "\n")
        self.stdout.flush()

    def handle_line(self, line):
        """Process a single JSON-RPC line; return the response dict (or None for blanks)."""
        line = line.strip()
        if not line:
            return None
        try:
            payload = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            return {"jsonrpc": "2.0", "id": None, "error": {"code": "parse_error", "message": "Invalid JSON."}}

        request_id = payload.get("id")
        method = payload.get("method")
        params = payload.get("params") or {}

        token = None
        if method not in PUBLIC_METHODS:
            token = self.token
            if token is None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": "unauthenticated", "message": "Missing or invalid MCP token."},
                }
        try:
            result = handle_method(token=token, method=method, params=params)
        except McpError as exc:
            return {"jsonrpc": "2.0", "id": request_id, "error": exc.to_dict()}
        except PermissionError as exc:
            return {"jsonrpc": "2.0", "id": request_id, "error": {"code": "unauthenticated", "message": str(exc)}}
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    def serve_forever(self):
        for line in self.stdin:
            response = self.handle_line(line)
            if response is not None:
                self._write(response)
