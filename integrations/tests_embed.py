from django.test import TestCase, override_settings

from integrations.polymarket.urls import get_polymarket_embed_slug
from integrations.polymarket.embed import (
    build_polymarket_embed_context,
    build_polymarket_embed_url,
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
        self.assertEqual(ctx["embed_slug"], "polymarket-native-slug")

    def test_manual_market_has_no_embed(self):
        manual = Market.objects.create(
            external_id="manual-1",
            title="Manual",
            slug="manual-market",
            source=Market.Source.MANUAL,
        )
        self.assertIsNone(build_polymarket_embed_context(manual))
