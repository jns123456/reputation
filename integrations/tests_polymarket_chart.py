from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

import requests

from integrations.polymarket.chart import (
    _fetch_price_points,
    build_polymarket_multi_outcome_chart_payload,
    build_polymarket_soccer_match_chart_payload,
)
from integrations.polymarket.client import (
    MULTI_OUTCOME_EVENT_KIND,
    build_polymarket_event_raw,
    normalize_polymarket_event_record,
    select_top_chart_outcomes,
)
from integrations.polymarket.embed import build_polymarket_embed_context
from markets.models import Market


def _grouped_market(label, market_id, yes_price, token_id):
    return {
        "id": market_id,
        "groupItemTitle": label,
        "groupItemThreshold": str(market_id),
        "closed": False,
        "outcomes": '["Yes", "No"]',
        "outcomePrices": f'["{yes_price}", "{1 - yes_price}"]',
        "clobTokenIds": f'["{token_id}"]',
        "slug": f"will-{label.lower()}-win",
    }


class FetchPricePointsTests(SimpleTestCase):
    @patch("integrations.polymarket.chart.time.sleep")
    @patch("integrations.polymarket.chart.requests.get")
    def test_retries_transient_timeout(self, mock_get, mock_sleep):
        success = MagicMock()
        success.status_code = 200
        success.json.return_value = {"history": [{"t": 1_700_000_000, "p": 0.42}]}
        mock_get.side_effect = [
            requests.exceptions.ReadTimeout("read timed out"),
            success,
        ]

        points = _fetch_price_points("token-a", interval="max", fidelity=1440)

        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["value"], 42.0)
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once_with(1)

    @patch("integrations.polymarket.chart.time.sleep")
    @patch("integrations.polymarket.chart.requests.get")
    def test_retries_chunked_encoding_error(self, mock_get, mock_sleep):
        success = MagicMock()
        success.status_code = 200
        success.json.return_value = {"history": [{"t": 1_700_000_000, "p": 0.42}]}
        mock_get.side_effect = [
            requests.exceptions.ChunkedEncodingError("Response ended prematurely"),
            success,
        ]

        points = _fetch_price_points("token-a", interval="max", fidelity=1440)

        self.assertEqual(len(points), 1)
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once_with(1)

    @patch("integrations.polymarket.chart.time.sleep")
    @patch("integrations.polymarket.chart.requests.get")
    @patch("integrations.services.logger")
    def test_logs_warning_after_exhausted_retries(self, mock_logger, mock_get, mock_sleep):
        mock_get.side_effect = requests.exceptions.ReadTimeout("read timed out")

        points = _fetch_price_points("token-a", interval="max", fidelity=1440)

        self.assertEqual(points, [])
        self.assertEqual(mock_get.call_count, 3)
        mock_logger.warning.assert_called_once()
        mock_logger.exception.assert_not_called()

    @patch("integrations.polymarket.chart.PolymarketClient")
    @patch("integrations.services.logger")
    def test_select_chart_outcomes_logs_warning_on_chunked_encoding_error(
        self, mock_logger, mock_client_class
    ):
        market = MagicMock()
        market.polymarket_slug = "demo-event"
        market.polymarket_raw = {"market_kind": MULTI_OUTCOME_EVENT_KIND}
        market.outcome_labels = ["Alpha", "Bravo"]
        market.current_probability = {}
        market.category = "Sports"

        mock_client = mock_client_class.return_value
        mock_client.fetch_event_by_slug.side_effect = requests.exceptions.ChunkedEncodingError(
            "Response ended prematurely"
        )

        from integrations.polymarket.chart import _select_chart_outcomes

        outcomes = _select_chart_outcomes(market, limit=4)

        self.assertEqual(outcomes, [])
        mock_logger.warning.assert_called_once()
        mock_logger.exception.assert_not_called()


class BuildPolymarketEventRawChartTests(SimpleTestCase):
    def test_stores_top_four_chart_outcomes_by_probability(self):
        event = {
            "slug": "tournament-winner",
            "title": "Tournament Winner",
            "volume": 1_000_000,
            "markets": [
                _grouped_market("Alpha", 1, 0.40, "token-a"),
                _grouped_market("Bravo", 2, 0.25, "token-b"),
                _grouped_market("Charlie", 3, 0.15, "token-c"),
                _grouped_market("Delta", 4, 0.10, "token-d"),
                _grouped_market("Echo", 5, 0.05, "token-e"),
                _grouped_market("Foxtrot", 6, 0.03, "token-f"),
            ],
        }
        normalized = normalize_polymarket_event_record(event)
        raw = build_polymarket_event_raw(event, normalized=normalized)

        self.assertEqual(len(raw["chart_outcomes"]), 4)
        self.assertEqual(
            [item["label"] for item in raw["chart_outcomes"]],
            ["Alpha", "Bravo", "Charlie", "Delta"],
        )
        self.assertEqual(raw["chart_outcomes"][0]["yes_token_id"], "token-a")
        self.assertEqual(raw["outcome_markets"]["Echo"]["yes_token_id"], "token-e")


class PolymarketMultiOutcomeChartTests(TestCase):
    def setUp(self):
        self.market = Market.objects.create(
            external_id="pm-event:tournament-winner",
            title="Tournament Winner",
            slug="tournament-winner",
            polymarket_slug="tournament-winner",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            outcomes=[
                {"label": "Alpha"},
                {"label": "Bravo"},
                {"label": "Charlie"},
                {"label": "Delta"},
                {"label": "Echo"},
            ],
            current_probability={
                "Alpha": 0.40,
                "Bravo": 0.25,
                "Charlie": 0.15,
                "Delta": 0.10,
                "Echo": 0.05,
            },
            polymarket_raw={
                "market_kind": MULTI_OUTCOME_EVENT_KIND,
                "chart_outcomes": [
                    {"label": "Alpha", "probability": 0.40, "slug": "alpha", "yes_token_id": "token-a"},
                    {"label": "Bravo", "probability": 0.25, "slug": "bravo", "yes_token_id": "token-b"},
                    {"label": "Charlie", "probability": 0.15, "slug": "charlie", "yes_token_id": "token-c"},
                    {"label": "Delta", "probability": 0.10, "slug": "delta", "yes_token_id": "token-d"},
                ],
                "volumeNum": 1_300_000_000,
            },
        )

    def test_select_top_chart_outcomes_uses_stored_payload(self):
        outcomes = select_top_chart_outcomes(self.market, limit=4)
        self.assertEqual([item["label"] for item in outcomes], ["Alpha", "Bravo", "Charlie", "Delta"])

    @patch("integrations.polymarket.chart._fetch_price_points")
    def test_build_multi_outcome_chart_payload(self, mock_fetch):
        now = timezone.now()
        mock_fetch.side_effect = [
            [{"ts": now, "value": 40.0}],
            [{"ts": now, "value": 25.0}],
            [{"ts": now, "value": 15.0}],
            [{"ts": now, "value": 10.0}],
        ]

        payload = build_polymarket_multi_outcome_chart_payload(self.market)
        self.assertIsNotNone(payload)
        self.assertEqual(len(payload["series"]), 4)
        self.assertEqual(payload["series"][0]["label"], "Alpha")
        self.assertEqual(payload["volume_label"], "$1.3b Vol.")

    @patch("integrations.polymarket.embed.build_polymarket_multi_outcome_chart_payload")
    def test_embed_context_uses_multi_outcome_chart(self, mock_chart):
        mock_chart.return_value = {"series": [{"label": "Alpha", "points": []}]}
        ctx = build_polymarket_embed_context(self.market)
        self.assertEqual(ctx["embed_kind"], "multi_outcome_chart")
        self.assertIn("chart_data", ctx)
        self.assertNotIn("embed_url", ctx)

    @patch("integrations.polymarket.chart._fetch_price_points")
    @patch("integrations.polymarket.chart.PolymarketClient")
    def test_chart_backfills_older_multi_outcome_imports(self, mock_client_class, mock_fetch):
        old_market = Market.objects.create(
            external_id="pm-event:nba-champion",
            title="NBA Champion",
            slug="nba-champion",
            polymarket_slug="nba-champion",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            outcomes=[
                {"label": "Alpha"},
                {"label": "Bravo"},
                {"label": "Charlie"},
                {"label": "Delta"},
            ],
            current_probability={
                "Alpha": 0.40,
                "Bravo": 0.25,
                "Charlie": 0.15,
                "Delta": 0.10,
            },
            polymarket_raw={
                "market_kind": MULTI_OUTCOME_EVENT_KIND,
                "event_slug": "nba-champion",
                "outcome_markets": {
                    "Alpha": {"slug": "alpha"},
                    "Bravo": {"slug": "bravo"},
                    "Charlie": {"slug": "charlie"},
                    "Delta": {"slug": "delta"},
                },
            },
        )
        mock_client = mock_client_class.return_value
        mock_client.fetch_event_by_slug.return_value = {
            "slug": "nba-champion",
            "title": "NBA Champion",
            "volume": 250_000_000,
            "markets": [
                _grouped_market("Alpha", 1, 0.40, "token-a"),
                _grouped_market("Bravo", 2, 0.25, "token-b"),
                _grouped_market("Charlie", 3, 0.15, "token-c"),
                _grouped_market("Delta", 4, 0.10, "token-d"),
                _grouped_market("Echo", 5, 0.05, "token-e"),
            ],
        }
        now = timezone.now()
        mock_fetch.return_value = [{"ts": now, "value": 40.0}]

        payload = build_polymarket_multi_outcome_chart_payload(old_market)
        old_market.refresh_from_db()

        self.assertIsNotNone(payload)
        self.assertEqual(len(payload["series"]), 4)
        self.assertEqual(
            [item["label"] for item in old_market.polymarket_raw["chart_outcomes"]],
            ["Alpha", "Bravo", "Charlie", "Delta"],
        )
        self.assertEqual(old_market.polymarket_raw["outcome_markets"]["Alpha"]["yes_token_id"], "token-a")


class PolymarketSoccerMatchChartTests(TestCase):
    def setUp(self):
        self.market = Market.objects.create(
            external_id="wc-match:col-cri",
            title="Colombia vs Costa Rica",
            slug="colombia-vs-costa-rica",
            polymarket_slug="fif-col-cri-2026-06-01",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            outcomes=[
                {"label": "Colombia"},
                {"label": "Draw"},
                {"label": "Costa Rica"},
            ],
            current_probability={
                "Colombia": 0.86,
                "Draw": 0.11,
                "Costa Rica": 0.05,
            },
            polymarket_raw={
                "market_kind": "soccer_match_3way",
                "team_a": "Colombia",
                "team_b": "Costa Rica",
                "chart_outcomes": [
                    {"label": "Colombia", "probability": 0.86, "slug": "col", "yes_token_id": "token-col"},
                    {"label": "Costa Rica", "probability": 0.05, "slug": "cri", "yes_token_id": "token-cri"},
                ],
            },
        )

    @patch("integrations.polymarket.chart._fetch_price_points")
    def test_build_soccer_match_chart_payload_excludes_draw(self, mock_fetch):
        now = timezone.now()
        mock_fetch.side_effect = [
            [{"ts": now, "value": 86.0}],
            [{"ts": now, "value": 5.0}],
        ]

        payload = build_polymarket_soccer_match_chart_payload(self.market)
        self.assertIsNotNone(payload)
        self.assertEqual(len(payload["series"]), 2)
        self.assertEqual([item["label"] for item in payload["series"]], ["Colombia", "Costa Rica"])
        self.assertEqual(payload["series"][0]["color"], "rgb(16 185 129)")
        self.assertEqual(payload["series"][1]["color"], "rgb(244 63 94)")

    @patch("integrations.polymarket.embed.build_polymarket_soccer_match_chart_payload")
    def test_embed_context_uses_soccer_match_chart(self, mock_chart):
        mock_chart.return_value = {"series": [{"label": "Colombia", "points": []}, {"label": "Costa Rica", "points": []}]}
        ctx = build_polymarket_embed_context(self.market)
        self.assertEqual(ctx["embed_kind"], "multi_outcome_chart")
        self.assertIn("chart_data", ctx)
        self.assertNotIn("embed_url", ctx)
