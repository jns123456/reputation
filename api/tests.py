"""REST API v1 tests."""

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import UserProfile
from conftest import create_market, create_user
from mcp.tokens import create_token
from predictions.models import Prediction


class ApiDocsPageTests(TestCase):
    def test_docs_page_renders(self):
        client = APIClient()
        resp = client.get("/api/docs/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "API documentation")
        self.assertContains(resp, "/api/v1/markets/")

    def test_docs_page_renders_in_spanish(self):
        client = APIClient()
        with self.settings(LANGUAGE_CODE="es"):
            resp = client.get("/api/docs/", HTTP_ACCEPT_LANGUAGE="es")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Documentación de la API")


class ApiDiscoveryTests(TestCase):
    def test_discovery_lists_v1_metadata(self):
        client = APIClient()
        resp = client.get("/api/v1/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["version"], "v1")
        self.assertIn("openapi_schema", resp.json())

    def test_reputation_event_serializer_binds_prediction_id(self):
        """Regression: redundant source='prediction_id' breaks drf-spectacular (PREDICTSTAMP-3)."""
        from api.v1.reputation import ReputationEventSerializer

        serializer = ReputationEventSerializer()
        self.assertIn("prediction_id", serializer.fields)


class ApiReadTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.market = create_market()
        self.user = create_user(username="reader")
        UserProfile.objects.get_or_create(user=self.user)

    def test_list_markets(self):
        resp = self.client.get("/api/v1/markets/")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.json()["count"], 1)

    def test_retrieve_market_by_slug(self):
        resp = self.client.get(f"/api/v1/markets/{self.market.slug}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["slug"], self.market.slug)

    def test_reputation_leaderboard(self):
        resp = self.client.get("/api/v1/leaderboards/reputation/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("results", resp.json())

    def test_rules_endpoints(self):
        resp = self.client.get("/api/v1/rules/reputation/")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["no_user_confidence"])


class ApiBearerAuthTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user(username="apiuser")
        self.market = create_market(slug="api-test-market", external_id="api-test-1")
        self.token, self.raw = create_token(
            user=self.user,
            name="test",
            scopes=["markets:read", "predictions:write", "comments:write"],
        )

    def test_bearer_auth_lists_markets(self):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.raw}")
        resp = self.client.get("/api/v1/markets/")
        self.assertEqual(resp.status_code, 200)

    def test_invalid_bearer_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer mcp_invalid_token")
        resp = self.client.get("/api/v1/markets/")
        self.assertEqual(resp.status_code, 401)


@override_settings(API_WRITES_ENABLED=True)
class ApiWriteTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_user(username="writer")
        self.market = create_market(
            slug="write-test-market",
            external_id="write-test-1",
            current_probability={"Yes": 0.4, "No": 0.6},
        )
        self.token, self.raw = create_token(
            user=self.user,
            name="writer",
            scopes=[
                "markets:read",
                "predictions:write",
                "comments:write",
                "votes:write",
                "social:write",
                "forum:write",
                "challenges:write",
            ],
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.raw}")

    def test_create_prediction(self):
        resp = self.client.post(
            "/api/v1/predictions/",
            {
                "market": self.market.slug,
                "predicted_outcome": "Yes",
                "predicted_direction": "yes",
                "reasoning": "API test forecast",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["predicted_outcome"], "Yes")
        self.assertTrue(
            Prediction.objects.filter(user=self.user, market=self.market).exists()
        )

    def test_prediction_dry_run(self):
        resp = self.client.post(
            "/api/v1/predictions/",
            {
                "market": self.market.slug,
                "predicted_outcome": "Yes",
                "dry_run": True,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["dry_run"])
        self.assertFalse(Prediction.objects.filter(user=self.user).exists())

    def test_create_comment(self):
        resp = self.client.post(
            "/api/v1/comments/",
            {"market": self.market.slug, "body": "API comment body"},
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["body"], "API comment body")

    def test_write_without_scope_denied(self):
        _token, raw = create_token(
            user=create_user(username="readonly"),
            name="ro",
            scopes=["markets:read"],
        )
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
        resp = self.client.post(
            "/api/v1/predictions/",
            {"market": self.market.slug, "predicted_outcome": "Yes"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)


@override_settings(API_WRITES_ENABLED=False)
class ApiWritesDisabledTests(TestCase):
    def test_writes_blocked_when_disabled(self):
        user = create_user(username="blocked")
        _token, raw = create_token(
            user=user,
            name="w",
            scopes=["predictions:write"],
        )
        market = create_market(slug="blocked-market", external_id="blocked-1")
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {raw}")
        resp = client.post(
            "/api/v1/predictions/",
            {"market": market.slug, "predicted_outcome": "Yes"},
            format="json",
        )
        self.assertEqual(resp.status_code, 403)
