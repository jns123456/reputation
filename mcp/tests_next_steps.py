"""Tests for the MCP developer-settings UI and the stdio transport (§17)."""

import io
import json

from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import AIAgentProfile, User
from conftest import create_user
from mcp.models import McpToken
from mcp.tokens import create_token
from mcp.transport import StdioMcpServer


class DeveloperSettingsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = create_user(username="dev")
        self.client.force_login(self.user)

    def test_create_token_shows_raw_once(self):
        resp = self.client.post(
            reverse("mcp:developer_settings"),
            {"name": "my-bot", "scopes": ["markets:read"]},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(McpToken.objects.filter(user=self.user).count(), 1)
        # Raw token surfaced exactly once on the post-redirect page...
        self.assertContains(resp, "Your new token")
        # ...and gone on the next plain GET (one-shot session flash).
        again = self.client.get(reverse("mcp:developer_settings"))
        self.assertNotContains(again, "Your new token")

    def test_human_cannot_grant_write_scope(self):
        resp = self.client.post(
            reverse("mcp:developer_settings"),
            {"name": "sneaky", "scopes": ["predictions:write"]},
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(McpToken.objects.filter(user=self.user).count(), 0)

    def test_revoke_token(self):
        token, _ = create_token(user=self.user, name="t", scopes=["markets:read"])
        resp = self.client.post(reverse("mcp:revoke_token", args=[token.id]))
        self.assertEqual(resp.status_code, 302)
        token.refresh_from_db()
        self.assertFalse(token.is_active)

    def test_rotate_token_revokes_old_and_creates_new(self):
        token, _ = create_token(user=self.user, name="t", scopes=["markets:read"])
        resp = self.client.post(reverse("mcp:rotate_token", args=[token.id]))
        self.assertEqual(resp.status_code, 302)
        token.refresh_from_db()
        self.assertFalse(token.is_active)
        self.assertEqual(McpToken.objects.filter(user=self.user, is_active=True).count(), 1)

    def test_cannot_revoke_another_users_token(self):
        other = create_user(username="other")
        token, _ = create_token(user=other, name="t", scopes=["markets:read"])
        resp = self.client.post(reverse("mcp:revoke_token", args=[token.id]))
        self.assertEqual(resp.status_code, 404)
        token.refresh_from_db()
        self.assertTrue(token.is_active)


class StdioTransportTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = create_user(username="agent", account_type=User.AccountType.DECLARED_AGENT)
        AIAgentProfile.objects.create(
            user=self.user,
            agent_name="agent",
            trust_level=AIAgentProfile.TrustLevel.STANDARD,
            rate_limit_tier="standard",
            allowed_scopes=["markets:read"],
        )
        self.token, self.raw = create_token(
            user=self.user, name="t", scopes=["markets:read"]
        )

    def _line(self, server, payload):
        return server.handle_line(json.dumps(payload))

    def test_initialize_is_public(self):
        server = StdioMcpServer(raw_token="")
        resp = self._line(server, {"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        self.assertIn("result", resp)
        self.assertEqual(resp["result"]["name"], "predictstamp-mcp")

    def test_tools_list_requires_token(self):
        server = StdioMcpServer(raw_token="")
        resp = self._line(server, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertEqual(resp["error"]["code"], "unauthenticated")

    def test_authenticated_tools_list(self):
        server = StdioMcpServer(raw_token=self.raw)
        resp = self._line(server, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        self.assertIn("result", resp)
        self.assertTrue(any(t["name"] == "search_markets" for t in resp["result"]["tools"]))

    def test_invalid_json_returns_parse_error(self):
        server = StdioMcpServer(raw_token="")
        resp = server.handle_line("{not json")
        self.assertEqual(resp["error"]["code"], "parse_error")

    def test_serve_forever_reads_stream(self):
        stdin = io.StringIO(
            json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}) + "\n"
        )
        stdout = io.StringIO()
        StdioMcpServer(raw_token="", stdin=stdin, stdout=stdout).serve_forever()
        out = json.loads(stdout.getvalue().strip())
        self.assertEqual(out["result"]["name"], "predictstamp-mcp")


class McpNavDiscoverabilityTests(TestCase):
    def setUp(self):
        self.agent = create_user(
            username="bagagent",
            account_type=User.AccountType.DECLARED_AGENT,
        )
        AIAgentProfile.objects.create(
            user=self.agent,
            agent_name="bagagent",
            trust_level=AIAgentProfile.TrustLevel.NEW,
        )
        self.visitor = create_user(username="visitor")
        self.client = Client()
        self.mcp_url = reverse("mcp:developer_settings")

    def test_profile_shows_mcp_link_for_owner(self):
        self.client.force_login(self.agent)
        response = self.client.get(
            reverse("accounts:profile", kwargs={"username": self.agent.username})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.mcp_url)
        self.assertContains(response, "Developers")
        self.assertContains(response, "Connect this agent")
        self.assertContains(response, "Manage MCP tokens")

    def test_profile_hides_agent_callout_for_other_users(self):
        self.client.force_login(self.visitor)
        response = self.client.get(
            reverse("accounts:profile", kwargs={"username": self.agent.username})
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Connect this agent")
        self.assertNotContains(response, "Manage MCP tokens")

    def test_navbar_shows_mcp_link_when_authenticated(self):
        self.client.force_login(self.agent)
        response = self.client.get(reverse("markets:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.mcp_url)
        self.assertContains(response, "Developers")

    def test_profile_mcp_nav_renders_in_spanish(self):
        self.client.force_login(self.agent)
        with self.settings(LANGUAGE_CODE="es"):
            response = self.client.get(
                reverse("accounts:profile", kwargs={"username": self.agent.username}),
                HTTP_ACCEPT_LANGUAGE="es",
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.mcp_url)
        self.assertContains(response, "Conectar este agente")
