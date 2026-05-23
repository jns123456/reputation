from unittest.mock import patch

from django.test import TestCase, override_settings

from integrations.kalshi.chart import build_kalshi_chart_payload, _normalize_trades
from integrations.kalshi.embed import build_kalshi_embed_context
from markets.models import Market


class KalshiChartTests(TestCase):
    def test_normalize_trades_builds_sorted_series(self):
        trades = [
            {"created_time": "2026-05-23T20:00:00Z", "yes_price_dollars": "0.6200"},
            {"created_time": "2026-05-23T19:00:00Z", "yes_price_dollars": "0.5300"},
        ]
        points = _normalize_trades(trades)
        self.assertEqual(len(points), 2)
        self.assertEqual(points[0]["value"], 53.0)
        self.assertEqual(points[1]["value"], 62.0)

    @patch("integrations.kalshi.chart.KalshiClient")
    def test_build_kalshi_chart_payload_from_trades(self, mock_client_cls):
        mock_client = mock_client_cls.return_value
        mock_client.fetch_candlesticks.return_value = []
        mock_client.fetch_trades.return_value = [
            {"created_time": "2026-05-23T19:00:00Z", "yes_price_dollars": "0.3800"},
            {"created_time": "2026-05-23T20:00:00Z", "yes_price_dollars": "0.4100"},
        ]

        market = Market.objects.create(
            external_id="KXTEST-CHART",
            title="Chart market",
            slug="chart-market",
            source=Market.Source.KALSHI,
            status=Market.Status.OPEN,
            outcomes=[{"label": "Pittsburgh"}, {"label": "Atlanta"}],
            current_probability={"Pittsburgh": 0.41, "Atlanta": 0.59},
            kalshi_ticker="KXTEST-CHART",
            kalshi_raw={"ticker": "KXTEST-CHART", "event_ticker": "KXTEST-EVENT"},
            kalshi_event_raw={"event": {"series_ticker": "KXTEST"}},
        )

        payload = build_kalshi_chart_payload(market)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["yes_label"], "Pittsburgh")
        self.assertEqual(payload["values"], [38.0, 41.0])


class KalshiEmbedTests(TestCase):
    @override_settings(KALSHI_EMBED_HEIGHT=420)
    @patch("integrations.kalshi.embed.build_kalshi_chart_payload")
    def test_build_kalshi_embed_context(self, mock_chart):
        mock_chart.return_value = {
            "labels": ["May 23 19:00"],
            "values": [38.0],
            "yes_label": "Pittsburgh",
            "current_percent": 38.0,
            "volume_label": "$1K Vol.",
            "ticker": "KXTEST-CHART",
        }
        market = Market.objects.create(
            external_id="KXTEST-EMBED",
            title="Embed market",
            slug="embed-market",
            source=Market.Source.KALSHI,
            kalshi_ticker="KXTEST-EMBED",
            kalshi_raw={"ticker": "KXTEST-EMBED", "event_ticker": "KXTEST-EVENT"},
            kalshi_event_raw={"event": {"series_ticker": "KXTEST"}},
        )

        ctx = build_kalshi_embed_context(market)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx["embed_height"], 420)
        self.assertIn("kalshi.com", ctx["kalshi_url"])

    def test_polymarket_market_has_no_kalshi_embed(self):
        market = Market.objects.create(
            external_id="poly-no-kalshi",
            title="Poly",
            slug="poly-no-kalshi",
            source=Market.Source.POLYMARKET,
        )
        self.assertIsNone(build_kalshi_embed_context(market))
