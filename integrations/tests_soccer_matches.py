from django.test import TestCase
from unittest.mock import patch

from integrations.polymarket.soccer_matches import (
    DRAW_OUTCOME_LABEL,
    WORLD_CUP_MATCH_EXTERNAL_PREFIX,
    build_world_cup_match_raw,
    classify_moneyline_outcome,
    is_world_cup_match_event,
    normalize_world_cup_match_event,
    parse_match_teams,
)
from integrations.services import import_market_from_normalized, sync_world_cup_match_markets
from markets.models import Market


MEXICO_VS_RSA_EVENT = {
    "slug": "fifwc-mex-rsa-2026-06-11",
    "title": "Mexico vs. South Africa",
    "startDate": "2026-06-11T19:00:00Z",
    "endDate": "2026-06-11T21:00:00Z",
    "volume24hr": 21240,
    "markets": [
        {
            "id": "m1",
            "question": "Will Mexico win on 2026-06-11?",
            "sportsMarketType": "moneyline",
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["0.665", "0.335"]',
            "closed": False,
        },
        {
            "id": "m2",
            "question": "Will Mexico vs. South Africa end in a draw?",
            "sportsMarketType": "moneyline",
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["0.215", "0.785"]',
            "closed": False,
        },
        {
            "id": "m3",
            "question": "Will South Africa win on 2026-06-11?",
            "sportsMarketType": "moneyline",
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["0.125", "0.875"]',
            "closed": False,
        },
    ],
}


class SoccerMatchNormalizationTests(TestCase):
    def test_parse_match_teams(self):
        self.assertEqual(parse_match_teams("Mexico vs. South Africa"), ("Mexico", "South Africa"))
        self.assertEqual(parse_match_teams("Brazil vs Morocco"), ("Brazil", "Morocco"))

    def test_classify_moneyline_outcome(self):
        team_a, team_b = "Mexico", "South Africa"
        self.assertEqual(
            classify_moneyline_outcome("Will Mexico win on 2026-06-11?", team_a, team_b),
            "Mexico",
        )
        self.assertEqual(
            classify_moneyline_outcome("Will Mexico vs. South Africa end in a draw?", team_a, team_b),
            DRAW_OUTCOME_LABEL,
        )
        self.assertEqual(
            classify_moneyline_outcome("Will South Africa win on 2026-06-11?", team_a, team_b),
            "South Africa",
        )

    def test_is_world_cup_match_event(self):
        self.assertTrue(is_world_cup_match_event(MEXICO_VS_RSA_EVENT))
        self.assertFalse(is_world_cup_match_event({"title": "Mexico vs. South Africa - More Markets", "markets": []}))

    def test_normalize_world_cup_match_event(self):
        normalized = normalize_world_cup_match_event(MEXICO_VS_RSA_EVENT)
        self.assertIsNotNone(normalized)
        self.assertEqual(normalized["external_id"], f"{WORLD_CUP_MATCH_EXTERNAL_PREFIX}fifwc-mex-rsa-2026-06-11")
        self.assertEqual([item["label"] for item in normalized["outcomes"]], ["Mexico", DRAW_OUTCOME_LABEL, "South Africa"])
        self.assertAlmostEqual(normalized["current_probability"]["Mexico"], 0.665)
        self.assertAlmostEqual(normalized["current_probability"][DRAW_OUTCOME_LABEL], 0.215)
        self.assertAlmostEqual(normalized["current_probability"]["South Africa"], 0.125)

    def test_import_world_cup_match_market(self):
        normalized = normalize_world_cup_match_event(MEXICO_VS_RSA_EVENT)
        raw_market = build_world_cup_match_raw(MEXICO_VS_RSA_EVENT, normalized=normalized)
        market, created = import_market_from_normalized(
            normalized,
            raw_market=raw_market,
            raw_event=MEXICO_VS_RSA_EVENT,
        )
        self.assertTrue(created)
        self.assertTrue(market.is_soccer_match)
        self.assertEqual(market.canonical_category_slug, "fifa-world-cup-2026")
        self.assertEqual(len(market.outcome_labels), 3)


class SyncWorldCupMatchMarketsTests(TestCase):
    @patch("integrations.services.PolymarketClient.fetch_world_cup_match_events")
    def test_sync_world_cup_match_markets(self, mock_fetch):
        mock_fetch.return_value = [MEXICO_VS_RSA_EVENT]
        result = sync_world_cup_match_markets(limit=5)
        mock_fetch.assert_called_once_with(limit=5)
        self.assertEqual(len(result["imported"]), 1)
        market = result["imported"][0]["market"]
        self.assertEqual(market.external_id, f"{WORLD_CUP_MATCH_EXTERNAL_PREFIX}fifwc-mex-rsa-2026-06-11")
        self.assertTrue(Market.objects.filter(external_id=market.external_id).exists())

    @patch("integrations.polymarket.client.PolymarketClient.fetch_events")
    def test_fetch_world_cup_match_events_paginates(self, mock_fetch_events):
        from integrations.polymarket.client import PolymarketClient

        def make_match(slug):
            event = dict(MEXICO_VS_RSA_EVENT)
            event["slug"] = slug
            event["title"] = f"Team Home vs. Team Away {slug}"
            return event

        page_one = [{"slug": "prop-1", "title": "Will Spain win?", "markets": []}]
        page_one.extend(make_match(f"match-{idx}") for idx in range(100))
        page_two = [make_match("match-final")]
        mock_fetch_events.side_effect = [page_one, page_two]

        client = PolymarketClient()
        matches = client.fetch_world_cup_match_events()
        self.assertEqual(len(matches), 101)
        self.assertEqual(mock_fetch_events.call_count, 2)
