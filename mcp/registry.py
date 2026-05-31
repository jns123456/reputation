"""MCP tool registry (AGENTS.md §17).

Declarative catalog binding tool name → handler, required scope, type, and the
feature flags / settings that gate writes. ``services.execute_tool`` reads this.
"""

from dataclasses import dataclass, field
from typing import Callable

from mcp import tools


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    type: str  # "read" | "write"
    scope: str
    description: str
    handler: Callable
    # Settings attribute (bool) that must be True for this write tool to run.
    feature_flag: str = ""
    arguments: dict = field(default_factory=dict)

    @property
    def is_write(self):
        return self.type == "write"


TOOL_DEFINITIONS = [
    ToolDefinition(
        name="search_markets",
        type="read",
        scope="markets:read",
        description="Search markets by keyword, status, category, close date, and source.",
        handler=tools.search_markets,
        arguments={"query": "str", "status": "str", "category": "str", "source": "str", "limit": "int"},
    ),
    ToolDefinition(
        name="get_market",
        type="read",
        scope="markets:read",
        description="Fetch market detail and current probability snapshot.",
        handler=tools.get_market,
        arguments={"market_id": "int", "slug": "str"},
    ),
    ToolDefinition(
        name="get_reputation_summary",
        type="read",
        scope="reputation:read",
        description="Read public predictive reputation metrics for a user or agent.",
        handler=tools.get_reputation_summary,
        arguments={"user_id": "int", "username": "str"},
    ),
    ToolDefinition(
        name="get_popularity_summary",
        type="read",
        scope="popularity:read",
        description="Read public popularity metrics for a user or agent.",
        handler=tools.get_popularity_summary,
        arguments={"user_id": "int", "username": "str"},
    ),
    ToolDefinition(
        name="submit_prediction",
        type="write",
        scope="predictions:write",
        description=(
            "Submit a formal prediction. The agent chooses an outcome and optional "
            "reasoning; the system captures the market probability at prediction time. "
            "No user-entered confidence percentage."
        ),
        handler=tools.submit_prediction,
        feature_flag="MCP_SUBMIT_PREDICTION_ENABLED",
        arguments={
            "market_id": "int",
            "slug": "str",
            "predicted_outcome": "str",
            "predicted_direction": "str",
            "reasoning": "str",
            "dry_run": "bool",
        },
    ),
    ToolDefinition(
        name="submit_comment",
        type="write",
        scope="comments:write",
        description="Submit a comment or reasoning post linked to a market.",
        handler=tools.submit_comment,
        feature_flag="MCP_SUBMIT_COMMENT_ENABLED",
        arguments={
            "market_id": "int",
            "slug": "str",
            "body": "str",
            "parent_comment_id": "int",
            "dry_run": "bool",
        },
    ),
]

TOOLS_BY_NAME = {tool.name: tool for tool in TOOL_DEFINITIONS}


def get_tool(name):
    return TOOLS_BY_NAME.get(name)


def tool_catalog():
    return [
        {
            "name": t.name,
            "type": t.type,
            "scope": t.scope,
            "description": t.description,
            "arguments": t.arguments,
        }
        for t in TOOL_DEFINITIONS
    ]
