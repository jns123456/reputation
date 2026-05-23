from django.test import TestCase

from integrations.kalshi.client import normalize_kalshi_record
from integrations.services import import_market_from_normalized
from markets.models import Market


class KalshiNormalizationTests(TestCase):
    def test_normalize_active_binary_market(self):
        raw = {
            "ticker": "KXDOTA2GAME-26MAY240700AURTS-TS",
            "title": "Will Team Spirit win the match?",
            "market_type": "binary",
            "status": "active",
            "yes_sub_title": "Team Spirit",
            "no_sub_title": "Team Spirit loses",
            "yes_bid_dollars": "0.5300",
            "yes_ask_dollars": "0.9200",
            "last_price_dollars": "0.0000",
            "close_time": "2026-06-07T11:00:00Z",
            "rules_primary": "If Team Spirit wins, market resolves to Yes.",
            "event_ticker": "KXDOTA2GAME-26MAY240700AURTS",
        }
        raw_event = {
            "event": {
                "category": "Sports",
                "series_ticker": "KXDOTA2GAME",
            }
        }

        normalized = normalize_kalshi_record(raw, raw_event=raw_event)

        self.assertEqual(normalized["external_id"], "KXDOTA2GAME-26MAY240700AURTS-TS")
        self.assertEqual(normalized["source"], "kalshi")
        self.assertEqual(normalized["status"], "open")
        self.assertEqual(normalized["category"], "Sports")
        self.assertEqual(normalized["outcomes"][0]["label"], "Team Spirit")
        self.assertAlmostEqual(normalized["current_probability"]["Team Spirit"], 0.725)

    def test_normalize_duplicate_sub_titles_use_distinct_labels(self):
        raw = {
            "ticker": "KXPAYROLLS-26MAY-T110000",
            "title": "Will above 110000 jobs be added in May 2026?",
            "market_type": "binary",
            "status": "active",
            "yes_sub_title": "Above 110,000",
            "no_sub_title": "Above 110,000",
            "last_price_dollars": "0.2300",
            "yes_bid_dollars": "0.2200",
            "yes_ask_dollars": "0.2300",
        }

        normalized = normalize_kalshi_record(raw)

        self.assertEqual(normalized["outcomes"][0]["label"], "Above 110,000")
        self.assertEqual(normalized["outcomes"][1]["label"], "At or below 110,000")
        self.assertAlmostEqual(normalized["current_probability"]["Above 110,000"], 0.23)
        self.assertAlmostEqual(normalized["current_probability"]["At or below 110,000"], 0.77)

    def test_normalize_resolved_market(self):
        raw = {
            "ticker": "KXMLBSPREAD-26MAY221840STLCIN-STL6",
            "title": "Cardinals wins by over 5.5 runs?",
            "market_type": "binary",
            "status": "finalized",
            "yes_sub_title": "Cardinals wins by over 5.5 runs",
            "no_sub_title": "Cardinals wins by over 5.5 runs",
            "result": "yes",
            "settlement_ts": "2026-05-23T20:02:31.607167Z",
        }

        normalized = normalize_kalshi_record(raw)

        self.assertEqual(normalized["status"], "resolved")
        self.assertEqual(normalized["resolved_outcome"], "Yes")
        self.assertIsNotNone(normalized["resolution_date"])


class KalshiImportServiceTests(TestCase):
    def test_import_creates_kalshi_market(self):
        data = {
            "external_id": "KXTEST-123",
            "title": "Kalshi Imported Market",
            "description": "Rules",
            "category": "Sports",
            "source": "kalshi",
            "status": "open",
            "outcomes": [{"label": "Yes"}, {"label": "No"}],
            "current_probability": {"Yes": 0.6, "No": 0.4},
            "close_date": None,
            "resolution_date": None,
            "resolved_outcome": "",
            "kalshi_ticker": "KXTEST-123",
        }
        raw_market = {"ticker": "KXTEST-123", "event_ticker": "KXTEST"}

        market, created = import_market_from_normalized(
            data,
            raw_market=raw_market,
            raw_event={"event": {"category": "Sports"}},
        )

        self.assertTrue(created)
        self.assertEqual(market.source, Market.Source.KALSHI)
        self.assertEqual(market.kalshi_ticker, "KXTEST-123")
        self.assertTrue(market.kalshi_raw)
        self.assertTrue(market.kalshi_synced_at)
