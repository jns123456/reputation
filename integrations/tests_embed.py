from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings

from integrations.polymarket.client import MULTI_OUTCOME_EVENT_KIND
from integrations.polymarket.urls import get_polymarket_embed_slug
from integrations.polymarket.embed import (
    build_polymarket_embed_context,
    build_polymarket_embed_url,
    build_polymarket_sports_embed_url,
)
from markets.models import Market


class PolymarketEmbedTests(TestCase):
    def setUp(self):
        self.market = Market.objects.create(
            external_id="embed-1",
            title="Test embed market",
            slug="test-embed-market",
            polymarket_slug="polymarket-native-slug",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
        )

    def test_get_polymarket_embed_slug_prefers_polymarket_slug(self):
        self.assertEqual(get_polymarket_embed_slug(self.market), "polymarket-native-slug")

    @override_settings(
        POLYMARKET_EMBED_THEME="light",
        POLYMARKET_EMBED_FEATURES="chart,volume",
        POLYMARKET_EMBED_LAYOUT="standard",
        POLYMARKET_EMBED_BORDER=True,
        POLYMARKET_EMBED_CONTENT_WIDTH=1200,
    )
    def test_build_polymarket_embed_url(self):
        url = build_polymarket_embed_url("my-market-slug")
        self.assertIn("embed.polymarket.com/market", url)
        self.assertIn("market=my-market-slug", url)
        self.assertIn("theme=light", url)
        self.assertIn("features=chart%2Cvolume", url)
        self.assertIn("width=1200", url)

    def test_build_polymarket_embed_context(self):
        ctx = build_polymarket_embed_context(self.market)
        self.assertIsNotNone(ctx)
        self.assertIn("embed.polymarket.com", ctx["embed_url"])
        self.assertIn("theme=light", ctx["embed_url_light"])
        self.assertIn("theme=dark", ctx["embed_url_dark"])
        self.assertEqual(ctx["embed_slug"], "polymarket-native-slug")

    def test_manual_market_has_no_embed(self):
        manual = Market.objects.create(
            external_id="manual-1",
            title="Manual",
            slug="manual-market",
            source=Market.Source.MANUAL,
        )
        self.assertIsNone(build_polymarket_embed_context(manual))

    @override_settings(
        POLYMARKET_EMBED_THEME="light",
        POLYMARKET_EMBED_BORDER=True,
        POLYMARKET_EMBED_CONTENT_WIDTH=1200,
        POLYMARKET_EMBED_HEIGHT=420,
    )
    def test_build_polymarket_sports_embed_url(self):
        url = build_polymarket_sports_embed_url("fifwc-esp-ksa-2026-06-21")
        self.assertIn("embed.polymarket.com/sports", url)
        self.assertIn("market=fifwc-esp-ksa-2026-06-21", url)
        self.assertIn("theme=light", url)
        self.assertIn("buttons=false", url)
        self.assertIn("height=420", url)

    def test_world_cup_match_uses_sports_embed(self):
        match = Market.objects.create(
            external_id="wc-match:fifwc-esp-ksa-2026-06-21",
            title="Spain vs. Saudi Arabia",
            slug="spain-vs-saudi-arabia",
            polymarket_slug="fifwc-esp-ksa-2026-06-21",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            outcomes=[{"label": "Spain"}, {"label": "Draw"}, {"label": "Saudi Arabia"}],
            polymarket_raw={"market_kind": "soccer_match_3way", "event_slug": "fifwc-esp-ksa-2026-06-21"},
        )
        ctx = build_polymarket_embed_context(match)
        self.assertIsNotNone(ctx)
        self.assertIn("embed.polymarket.com/sports", ctx["embed_url"])
        self.assertIn("theme=dark", ctx["embed_url_dark"])
        self.assertNotIn("embed.polymarket.com/market", ctx["embed_url"])

    @patch("integrations.polymarket.embed.build_polymarket_multi_outcome_chart_payload")
    def test_multi_outcome_event_uses_sports_embed_when_chart_unavailable(self, mock_chart):
        mock_chart.return_value = None
        event_market = Market.objects.create(
            external_id="pm-event:2026-mens-wimbledon-winner",
            title="2026 Men's Wimbledon Winner",
            slug="2026-mens-wimbledon-winner",
            polymarket_slug="2026-mens-wimbledon-winner",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            outcomes=[{"label": "Spain"}, {"label": "France"}, {"label": "England"}],
            polymarket_raw={
                "market_kind": MULTI_OUTCOME_EVENT_KIND,
                "event_slug": "2026-mens-wimbledon-winner",
                "slug": "2026-mens-wimbledon-winner",
            },
        )
        ctx = build_polymarket_embed_context(event_market)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx["embed_kind"], "iframe")
        self.assertIn("embed.polymarket.com/sports", ctx["embed_url"])
        self.assertIn("market=2026-mens-wimbledon-winner", ctx["embed_url"])
        self.assertNotIn("embed.polymarket.com/market", ctx["embed_url"])

    @patch("integrations.polymarket.embed.build_polymarket_multi_outcome_chart_payload")
    def test_multi_outcome_event_prefers_custom_chart(self, mock_chart):
        mock_chart.return_value = {
            "series": [{"label": "Spain", "points": [{"ts": "2026-01-01T00:00:00+00:00", "value": 17.0}]}],
        }
        event_market = Market.objects.create(
            external_id="pm-event:2026-mens-wimbledon-winner",
            title="2026 Men's Wimbledon Winner",
            slug="2026-mens-wimbledon-winner",
            polymarket_slug="2026-mens-wimbledon-winner",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            outcomes=[{"label": "Spain"}, {"label": "France"}, {"label": "England"}],
            polymarket_raw={"market_kind": MULTI_OUTCOME_EVENT_KIND},
        )
        ctx = build_polymarket_embed_context(event_market)
        self.assertEqual(ctx["embed_kind"], "multi_outcome_chart")
        self.assertIn("chart_data", ctx)
