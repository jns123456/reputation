"""Run the PredictStamp MCP server over stdio (AGENTS.md §17).

Usage (an MCP client launches this as a subprocess):

    python manage.py mcp_stdio --token <raw-mcp-token>

or set the ``MCP_TOKEN`` environment variable. All requests are dispatched
through ``mcp.services`` — identical scopes, gating, and audit logging as HTTP.
"""

import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from mcp.transport import StdioMcpServer


class Command(BaseCommand):
    help = "Serve the MCP API over stdio (newline-delimited JSON-RPC 2.0)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--token",
            default=os.environ.get("MCP_TOKEN", ""),
            help="Raw MCP bearer token (or set MCP_TOKEN).",
        )

    def handle(self, *args, **options):
        if not getattr(settings, "MCP_ENABLED", True):
            raise CommandError("MCP is disabled (MCP_ENABLED=False).")
        token = options.get("token") or ""
        server = StdioMcpServer(raw_token=token)
        if token and server.token is None:
            raise CommandError("Invalid or revoked MCP token.")
        # Authenticated agents still must hold scopes; public discovery works without a token.
        server.serve_forever()
