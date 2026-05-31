"""MCP dispatch service (AGENTS.md §17).

Single choke point for executing tools and reading resources. Enforces, in order:
feature flags → circuit breaker → scope → trust (writes) → rate limits → handler,
with ``dry_run`` support and a ``McpToolCallLog`` audit record for every call.

MCP must never bypass existing permissions, rate limits, scoring, moderation, or
MVP boundaries — it only orchestrates the checks and delegates to domain services.
"""

import hashlib
import json
import uuid
from dataclasses import dataclass

from django.conf import settings

from accounts import abuse_services
from accounts.agent_services import can_agent_write, is_write_scope
from accounts.risk_services import calculate_account_risk_score
from mcp.errors import McpError
from mcp.models import McpToolCallLog
from mcp.registry import get_tool
from mcp.resources import match_resource


@dataclass
class McpContext:
    user: object
    token: object
    dry_run: bool = False
    request_id: str = ""


def _input_hash(arguments):
    try:
        payload = json.dumps(arguments, sort_keys=True, default=str)
    except TypeError:
        payload = str(arguments)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _log(*, context, tool_name, arguments, status, error_code="", risk_score=0):
    user = context.user
    is_agent = bool(getattr(user, "is_agent_account", False))
    try:
        McpToolCallLog.objects.create(
            token=context.token,
            user=user if getattr(user, "is_authenticated", False) else None,
            agent_id=user.id if (is_agent and getattr(user, "id", None)) else None,
            tool_name=tool_name,
            input_hash=_input_hash(arguments),
            status=status,
            error_code=error_code or "",
            risk_score=risk_score,
            request_id=context.request_id or "",
        )
    except Exception:  # noqa: BLE001 - logging must not break the call
        pass


def _token_has_scope(token, scope):
    return scope in (token.scopes or [])


def _check_writes_enabled(tool):
    if not tool.is_write:
        return
    if not getattr(settings, "MCP_WRITES_ENABLED", False):
        raise McpError("writes_disabled", "MCP write tools are disabled.", http_status=403)
    if tool.feature_flag and not getattr(settings, tool.feature_flag, False):
        raise McpError(
            "tool_disabled",
            f"Tool '{tool.name}' is not enabled.",
            http_status=403,
        )


def execute_tool(*, context: McpContext, tool_name: str, arguments: dict = None):
    arguments = dict(arguments or {})
    # ``dry_run`` may arrive in the arguments or be set on the context.
    if "dry_run" in arguments:
        context.dry_run = bool(arguments.get("dry_run"))
    risk_score = (
        calculate_account_risk_score(context.user)
        if getattr(context.user, "is_authenticated", False)
        else 60
    )

    tool = get_tool(tool_name)
    if tool is None:
        _log(context=context, tool_name=tool_name, arguments=arguments,
             status=McpToolCallLog.Status.ERROR, error_code="unknown_tool", risk_score=risk_score)
        raise McpError("unknown_tool", f"Unknown tool: {tool_name}", http_status=404)

    breaker_name = f"mcp:{tool.name}"
    try:
        # 1. Feature flags (writes).
        _check_writes_enabled(tool)

        # 2. Circuit breaker (writes).
        if tool.is_write and abuse_services.is_circuit_open(breaker_name):
            raise McpError("circuit_open", "This tool is temporarily disabled due to abuse.", http_status=503)

        # 3. Token scope.
        if not _token_has_scope(context.token, tool.scope):
            raise McpError("insufficient_scope", f"Token lacks scope '{tool.scope}'.", http_status=403)

        # 4. Trust gate for writes.
        if is_write_scope(tool.scope) and not can_agent_write(context.user):
            raise McpError(
                "insufficient_trust",
                "Agent trust level is too low for write actions.",
                http_status=403,
            )

        # 5. Rate limits (every call; stricter bucket for writes).
        tier = context.token.rate_limit_tier or abuse_services.get_rate_limit_tier(context.user)
        identifier = f"token:{context.token.id}"
        abuse_services.enforce_rate_limit(
            action="mcp_call", user=context.user, identifier=identifier, tier=tier,
        )
        if tool.is_write:
            abuse_services.enforce_rate_limit(
                action="mcp_write", user=context.user, identifier=identifier, tier=tier,
            )

        # 6. Execute.
        result = tool.handler(context=context, arguments=arguments)

    except abuse_services.RateLimitExceeded as exc:
        _log(context=context, tool_name=tool.name, arguments=arguments,
             status=McpToolCallLog.Status.RATE_LIMITED, error_code=str(exc.action), risk_score=risk_score)
        raise McpError("rate_limited", "Rate limit exceeded.", http_status=429) from exc
    except McpError as exc:
        status = McpToolCallLog.Status.DENIED if exc.http_status in (403, 503) else McpToolCallLog.Status.ERROR
        if tool.is_write and exc.code in ("spam_rejected", "rejected"):
            abuse_services.register_abuse_signal(breaker_name)
        _log(context=context, tool_name=tool.name, arguments=arguments,
             status=status, error_code=exc.code, risk_score=risk_score)
        raise

    status = McpToolCallLog.Status.DRY_RUN if context.dry_run and tool.is_write else McpToolCallLog.Status.OK
    _log(context=context, tool_name=tool.name, arguments=arguments,
         status=status, risk_score=risk_score)
    return result


def read_resource(*, context: McpContext, uri: str):
    risk_score = (
        calculate_account_risk_score(context.user)
        if getattr(context.user, "is_authenticated", False)
        else 60
    )
    tool_label = f"resource:{uri}"
    try:
        handler, scope, kwargs = match_resource(uri)
        if not _token_has_scope(context.token, scope):
            raise McpError("insufficient_scope", f"Token lacks scope '{scope}'.", http_status=403)
        tier = context.token.rate_limit_tier or abuse_services.get_rate_limit_tier(context.user)
        abuse_services.enforce_rate_limit(
            action="mcp_call", user=context.user, identifier=f"token:{context.token.id}", tier=tier,
        )
        result = handler(**kwargs)
    except abuse_services.RateLimitExceeded as exc:
        _log(context=context, tool_name=tool_label, arguments={"uri": uri},
             status=McpToolCallLog.Status.RATE_LIMITED, error_code="mcp_call", risk_score=risk_score)
        raise McpError("rate_limited", "Rate limit exceeded.", http_status=429) from exc
    except McpError as exc:
        status = McpToolCallLog.Status.DENIED if exc.http_status in (403, 503) else McpToolCallLog.Status.ERROR
        _log(context=context, tool_name=tool_label, arguments={"uri": uri},
             status=status, error_code=exc.code, risk_score=risk_score)
        raise
    _log(context=context, tool_name=tool_label, arguments={"uri": uri},
         status=McpToolCallLog.Status.OK, risk_score=risk_score)
    return result


def new_request_id():
    return uuid.uuid4().hex
