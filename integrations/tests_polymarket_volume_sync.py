from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase, override_settings

from integrations.polymarket.client import (
    collect_binary_market_pairs_from_events,
    is_binary_market_record,
)
from integrations.services import sync_top_volume_polymarket_markets


def _binary_market(market_id, *, question="Will X happen?", closed=False):
    return {
        "id": market_id,
        "question": question,
        "closed": closed,
        "outcomes": '["Yes", "No"]',
        "volumeNum": 1000,
    }


class CollectBinaryMarketPairsTests(SimpleTestCase):
    def test_collects_binary_markets_with_parent_event(self):
        event = {
            "slug": "demo-event",
            "volume": 5000,
            "volume24hr": 250,
            "markets": [
                _binary_market("1"),
                {"id": "2", "question": "Three-way?", "outcomes": '["A", "B", "C"]'},
            ],
        }

        pairs = collect_binary_market_pairs_from_events([event], default_category="Politics")

        self.assertEqual(len(pairs), 1)
        market, parent = pairs[0]
        self.assertEqual(market["id"], "1")
        self.assertEqual(parent["slug"], "demo-event")
        self.assertEqual(market["volume24hr"], 250)

    def test_respects_limit_and_seen_ids(self):
        events = [
            {
                "volume24hr": 100,
                "markets": [_binary_market("1"), _binary_market("2")],
            }
        ]
        seen = {"2"}

        pairs = collect_binary_market_pairs_from_events(events, seen_ids=seen, limit=1)

        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0][0]["id"], "1")


class FetchTopVolumeMarketPairsTests(SimpleTestCase):
    @patch("integrations.polymarket.client.PolymarketClient.fetch_events_paginated")
    def test_stops_after_volume_share_threshold(self, mock_fetch):
        from integrations.polymarket.client import PolymarketClient

        mock_fetch.side_effect = [
            [
                {
                    "volume": 700,
                    "volume24hr": 70,
                    "markets": [_binary_market("a")],
                },
                {
                    "volume": 300,
                    "volume24hr": 30,
                    "markets": [_binary_market("b")],
                },
            ],
            [
                {
                    "volume": 50,
                    "volume24hr": 500,
                    "markets": [_binary_market("c")],
                },
            ],
        ]

        client = PolymarketClient()
        pairs = client.fetch_top_volume_market_pairs(
            min_volume_share=0.5,
            max_markets=100,
            max_event_pages=2,
            page_size=10,
        )

        ids = {market["id"] for market, _event in pairs}
        self.assertIn("a", ids)
        self.assertNotIn("b", ids)
        self.assertIn("c", ids)


@override_settings(
    POLYMARKET_TOP_VOLUME_MIN_SHARE=0.5,
    POLYMARKET_TOP_VOLUME_MAX_MARKETS=10,
    POLYMARKET_TOP_VOLUME_MAX_EVENT_PAGES=2,
)
class SyncTopVolumePolymarketMarketsTests(SimpleTestCase):
    @patch("integrations.services.import_market_from_normalized")
    @patch("integrations.services.PolymarketClient")
    def test_sync_imports_pairs_from_client(self, mock_client_cls, mock_import):
        mock_client = mock_client_cls.return_value
        mock_client.fetch_top_volume_market_pairs.return_value = [
            (_binary_market("99"), {"slug": "event-99", "volume": 999}),
        ]
        mock_import.return_value = (MagicMock(), True)

        result = sync_top_volume_polymarket_markets()

        self.assertEqual(len(result["imported"]), 1)
        mock_import.assert_called_once()
        self.assertEqual(mock_import.call_args.kwargs["raw_event"]["slug"], "event-99")


class BinaryMarketRecordTests(SimpleTestCase):
    def test_is_binary_market_record(self):
        self.assertTrue(is_binary_market_record(_binary_market("1")))
        self.assertFalse(
            is_binary_market_record(
                {"outcomes": '["A", "B", "C"]', "question": "Multi"},
            )
        )
