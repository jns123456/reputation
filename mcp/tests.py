"""Tests for the MCP layer: tokens, scopes, dry-run, rate limits, audit log (§17)."""

import json
from datetime import timedelta
from io import StringIO

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.agent_services import scopes_for_trust_level
from accounts.models import AIAgentProfile, User
from conftest import create_market, create_user
from mcp.errors import McpError
from mcp.models import McpToken, McpToolCallLog
from mcp.services import McpContext, execute_tool, read_resource
from mcp.tokens import create_token, hash_token, resolve_token
from predictions.models import Prediction


def make_agent_user(username="agent1", trust=AIAgentProfile.TrustLevel.STANDARD):
    user = create_user(username=username, account_type=User.AccountType.DECLARED_AGENT)
    profile = AIAgentProfile.objects.create(
        user=user,
        agent_name=username,
        trust_level=trust,
        rate_limit_tier="standard",
        allowed_scopes=scopes_for_trust_level(trust),
    )
    return user, profile


def context_for(token, dry_run=False):
    return McpContext(user=token.user, token=token, dry_run=dry_run, request_id="test")


class TokenTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = create_user(username="tok")

    def test_raw_token_is_hashed_at_rest(self):
        token, raw = create_token(user=self.user, name="t1", scopes=["markets:read"])
        self.assertNotEqual(token.token_hash, raw)
        self.assertEqual(token.token_hash, hash_token(raw))
        # The model never stores the raw value anywhere.
        self.assertNotIn(raw, json.dumps(list(McpToken.objects.values()), default=str))

    def test_resolve_valid_token(self):
        token, raw = create_token(user=self.user, name="t1", scopes=["markets:read"])
        resolved = resolve_token(raw)
        self.assertEqual(resolved.id, token.id)
        self.assertIsNotNone(resolved.last_used_at)

    def test_revoked_token_does_not_resolve(self):
        token, raw = create_token(user=self.user, name="t1", scopes=["markets:read"])
        token.revoke()
        self.assertIsNone(resolve_token(raw))

    def test_unknown_token_does_not_resolve(self):
        self.assertIsNone(resolve_token("mcp_deadbeef_nope"))


class ReadToolTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = create_user(username="reader")
        self.market = create_market()
        self.token, _ = create_token(
            user=self.user, name="r", scopes=["markets:read", "reputation:read"]
        )

    def test_search_markets_returns_results(self):
        result = execute_tool(
            context=context_for(self.token),
            tool_name="search_markets",
            arguments={},
        )
        self.assertGreaterEqual(result["count"], 1)

    def test_read_denied_without_scope(self):
        token, _ = create_token(user=self.user, name="noscope", scopes=["popularity:read"])
        with self.assertRaises(McpError) as ctx:
            execute_tool(context=context_for(token), tool_name="search_markets", arguments={})
        self.assertEqual(ctx.exception.code, "insufficient_scope")

    def test_read_resource_logs_call(self):
        before = McpToolCallLog.objects.count()
        read_resource(context=context_for(self.token), uri="platform://markets")
        self.assertEqual(McpToolCallLog.objects.count(), before + 1)


class WriteToolGatingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.market = create_market()
        self.agent, self.profile = make_agent_user()
        self.token, _ = create_token(
            user=self.agent,
            name="w",
            scopes=["markets:read", "predictions:write"],
        )

    def test_writes_disabled_by_default(self):
        with self.assertRaises(McpError) as ctx:
            execute_tool(
                context=context_for(self.token),
                tool_name="submit_prediction",
                arguments={"market_id": self.market.id, "predicted_outcome": "Yes"},
            )
        self.assertEqual(ctx.exception.code, "writes_disabled")

    @override_settings(MCP_WRITES_ENABLED=True, MCP_SUBMIT_PREDICTION_ENABLED=True)
    def test_dry_run_does_not_write(self):
        before = Prediction.objects.count()
        result = execute_tool(
            context=context_for(self.token, dry_run=True),
            tool_name="submit_prediction",
            arguments={"market_id": self.market.id, "predicted_outcome": "Yes", "dry_run": True},
        )
        self.assertTrue(result["dry_run"])
        self.assertEqual(Prediction.objects.count(), before)
        self.assertTrue(
            McpToolCallLog.objects.filter(
                tool_name="submit_prediction", status=McpToolCallLog.Status.DRY_RUN
            ).exists()
        )

    @override_settings(MCP_WRITES_ENABLED=True, MCP_SUBMIT_PREDICTION_ENABLED=True)
    def test_real_write_creates_prediction_with_snapshot(self):
        result = execute_tool(
            context=context_for(self.token),
            tool_name="submit_prediction",
            arguments={"market_id": self.market.id, "predicted_outcome": "Yes"},
        )
        prediction = Prediction.objects.get(pk=result["prediction_id"])
        self.assertEqual(prediction.user, self.agent)
        # Scoring input: the system captured the market probability snapshot,
        # not a user-entered confidence.
        self.assertEqual(prediction.probability_at_prediction_time, {"Yes": 0.3, "No": 0.7})

    @override_settings(MCP_WRITES_ENABLED=True, MCP_SUBMIT_PREDICTION_ENABLED=True)
    def test_write_denied_without_scope(self):
        token, _ = create_token(user=self.agent, name="readonly", scopes=["markets:read"])
        with self.assertRaises(McpError) as ctx:
            execute_tool(
                context=context_for(token),
                tool_name="submit_prediction",
                arguments={"market_id": self.market.id, "predicted_outcome": "Yes"},
            )
        self.assertEqual(ctx.exception.code, "insufficient_scope")

    @override_settings(MCP_WRITES_ENABLED=True, MCP_SUBMIT_PREDICTION_ENABLED=True)
    def test_write_denied_for_low_trust_agent(self):
        new_agent, profile = make_agent_user(username="newbie", trust=AIAgentProfile.TrustLevel.NEW)
        # Force the token to carry the write scope even though trust is too low.
        token, _ = create_token(
            user=new_agent, name="lowtrust", scopes=["markets:read", "predictions:write"]
        )
        with self.assertRaises(McpError) as ctx:
            execute_tool(
                context=context_for(token),
                tool_name="submit_prediction",
                arguments={"market_id": self.market.id, "predicted_outcome": "Yes"},
            )
        self.assertEqual(ctx.exception.code, "insufficient_trust")


@override_settings(ABUSE_RATE_LIMITS={"mcp_call": {"standard": (2, 3600)}})
class RateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = create_user(username="rl")
        self.market = create_market()
        self.token, _ = create_token(user=self.user, name="rl", scopes=["markets:read"])
        self.token.rate_limit_tier = "standard"
        self.token.save(update_fields=["rate_limit_tier"])

    def test_rate_limit_blocks_excess_calls(self):
        ctx = context_for(self.token)
        execute_tool(context=ctx, tool_name="search_markets", arguments={})
        execute_tool(context=ctx, tool_name="search_markets", arguments={})
        with self.assertRaises(McpError) as exc:
            execute_tool(context=ctx, tool_name="search_markets", arguments={})
        self.assertEqual(exc.exception.code, "rate_limited")


class HttpEndpointTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = create_user(username="http")
        self.token, self.raw = create_token(
            user=self.user, name="h", scopes=["markets:read"]
        )
        self.url = reverse("mcp:endpoint")
        create_market()

    def test_unauthenticated_call_is_rejected(self):
        resp = self.client.post(
            self.url,
            data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)

    def test_authenticated_tools_list(self):
        resp = self.client.post(
            self.url,
            data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.raw}",
        )
        self.assertEqual(resp.status_code, 200)
        names = [t["name"] for t in resp.json()["result"]["tools"]]
        self.assertIn("search_markets", names)

    def test_discovery_get_is_public(self):
        resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["name"], "predictstamp-mcp")
        self.assertFalse(resp.json()["writes_enabled"])


class PruneMcpLogsCommandTests(TestCase):
    def test_prune_mcp_logs_deletes_only_old_rows(self):
        user = create_user(username="prune")
        token, _ = create_token(user=user, name="prune", scopes=["markets:read"])
        old_log = McpToolCallLog.objects.create(
            token=token,
            user=user,
            tool_name="search_markets",
            status=McpToolCallLog.Status.OK,
        )
        McpToolCallLog.objects.filter(pk=old_log.pk).update(
            created_at=timezone.now() - timedelta(days=120)
        )
        recent_log = McpToolCallLog.objects.create(
            token=token,
            user=user,
            tool_name="get_market",
            status=McpToolCallLog.Status.OK,
        )

        call_command("prune_mcp_logs", "--days", "90", stdout=StringIO())

        self.assertFalse(McpToolCallLog.objects.filter(pk=old_log.pk).exists())
        self.assertTrue(McpToolCallLog.objects.filter(pk=recent_log.pk).exists())

    def test_prune_mcp_logs_dry_run_does_not_delete(self):
        user = create_user(username="prune-dry")
        token, _ = create_token(user=user, name="prune", scopes=["markets:read"])
        log = McpToolCallLog.objects.create(
            token=token,
            user=user,
            tool_name="search_markets",
            status=McpToolCallLog.Status.OK,
        )
        McpToolCallLog.objects.filter(pk=log.pk).update(
            created_at=timezone.now() - timedelta(days=120)
        )

        call_command("prune_mcp_logs", "--days", "90", "--dry-run", stdout=StringIO())

        self.assertTrue(McpToolCallLog.objects.filter(pk=log.pk).exists())
