"""Tests for Polymarket head-to-head (2-player moneyline) match import."""

from unittest.mock import patch

from django.test import TestCase

from integrations.polymarket.client import collect_importable_market_pairs_from_events
from integrations.polymarket.head_to_head_matches import (
    H2H_MATCH_EXTERNAL_PREFIX,
    build_h2h_match_raw,
    is_h2h_match_event,
    normalize_h2h_match_event,
)
from integrations.services import import_market_from_normalized, sync_h2h_match_markets
from markets.composite_redirect import get_composite_redirect_market, is_orphan_polymarket_leg
from markets.models import Market
from markets.selectors import filter_markets_by_browse_area, get_markets_list

UFC_H2H_EVENT = {
    "slug": "ufc-fight-night-belal-gabriel-2026-06-07",
    "title": "UFC Fight Night: Belal Muhammad vs. Gabriel Bonfim (Welterweight, Main Card)",
    "tags": [{"slug": "ufc"}, {"slug": "sports"}],
    "gameStartTime": "2026-06-07T22:00:00Z",
    "endDate": "2026-06-08T02:00:00Z",
    "markets": [
        {
            "id": "ml-ufc-1",
            "sportsMarketType": "moneyline",
            "question": "UFC Fight Night: Belal Muhammad vs. Gabriel Bonfim",
            "outcomes": '["Belal Muhammad", "Gabriel Bonfim"]',
            "outcomePrices": '["0.58", "0.42"]',
            "clobTokenIds": '["token-belal", "token-gabriel"]',
            "closed": False,
            "acceptingOrders": True,
            "gameStartTime": "2026-06-07T22:00:00Z",
        },
    ],
}

NBA_H2H_EVENT = {
    "slug": "nba-nyk-sas-2026-06-03",
    "title": "Knicks vs. Spurs",
    "tags": [{"slug": "nba"}, {"slug": "basketball"}, {"slug": "sports"}],
    "volume24hr": 500000,
    "gameStartTime": "2026-06-03T00:30:00Z",
    "endDate": "2026-06-03T04:00:00Z",
    "markets": [
        {
            "id": "ml-nba-1",
            "sportsMarketType": "moneyline",
            "question": "Knicks vs. Spurs",
            "outcomes": '["Knicks", "Spurs"]',
            "outcomePrices": '["0.55", "0.45"]',
            "clobTokenIds": '["token-knicks", "token-spurs"]',
            "closed": False,
            "acceptingOrders": True,
            "gameStartTime": "2026-06-03T00:30:00Z",
        },
    ],
}

TENNIS_H2H_EVENT = {
    "slug": "atp-testplayer-rival-2026-06-02",
    "title": "Roland Garros ATP: Test Player vs Other Player",
    "description": "Match winner",
    "tags": [{"slug": "tennis"}, {"slug": "sports"}],
    "volume": 12000,
    "volume24hr": 5000,
    "gameStartTime": "2026-06-02T14:00:00Z",
    "endDate": "2026-06-02T18:00:00Z",
    "markets": [
        {
            "id": "ml-tennis-1",
            "sportsMarketType": "moneyline",
            "question": "Roland Garros ATP: Test Player vs Other Player",
            "outcomes": '["Test Player", "Other Player"]',
            "outcomePrices": '["0.62", "0.38"]',
            "clobTokenIds": '["token-a", "token-b"]',
            "closed": False,
            "acceptingOrders": True,
            "gameStartTime": "2026-06-02T14:00:00Z",
            "endDate": "2026-06-02T18:00:00Z",
        },
        {
            "id": "prop-completed",
            "sportsMarketType": "tennis_completed_match",
            "question": "Completed Match: Test Player vs Other Player",
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["0.5", "0.5"]',
            "closed": False,
        },
    ],
}


class HeadToHeadMatchDetectionTests(TestCase):
    def test_is_h2h_match_event_nba(self):
        self.assertTrue(is_h2h_match_event(NBA_H2H_EVENT))

    def test_is_h2h_match_event_ufc(self):
        self.assertTrue(is_h2h_match_event(UFC_H2H_EVENT))

    def test_is_h2h_match_event(self):
        self.assertTrue(is_h2h_match_event(TENNIS_H2H_EVENT))
        self.assertFalse(is_h2h_match_event({"title": "2026 Men's French Open Winner", "markets": []}))

    def test_normalize_h2h_match_event(self):
        normalized = normalize_h2h_match_event(TENNIS_H2H_EVENT)
        self.assertIsNotNone(normalized)
        self.assertEqual(normalized["external_id"], f"{H2H_MATCH_EXTERNAL_PREFIX}atp-testplayer-rival-2026-06-02")
        self.assertEqual(
            set(normalized["current_probability"].keys()),
            {"Test Player", "Other Player"},
        )
        self.assertEqual(normalized["status"], "open")

    def test_collect_importable_prefers_h2h_composite(self):
        pairs = collect_importable_market_pairs_from_events([TENNIS_H2H_EVENT], limit=10)
        self.assertEqual(len(pairs), 1)
        raw_market, _event = pairs[0]
        self.assertEqual(raw_market.get("market_kind"), "h2h_match_2way")
        self.assertEqual(raw_market.get("team_a"), "Test Player")


@patch("markets.translation_services.translate_market_copy", side_effect=lambda text: text)
class HeadToHeadMatchImportTests(TestCase):
    def test_import_h2h_match_market(self, _mock_translate):
        normalized = normalize_h2h_match_event(TENNIS_H2H_EVENT)
        raw_market = build_h2h_match_raw(TENNIS_H2H_EVENT, normalized=normalized)
        market, created = import_market_from_normalized(
            normalized,
            raw_market=raw_market,
            raw_event=TENNIS_H2H_EVENT,
        )
        self.assertTrue(created)
        self.assertEqual(market.external_id, f"{H2H_MATCH_EXTERNAL_PREFIX}atp-testplayer-rival-2026-06-02")
        self.assertIn("tennis", market.browse_area_slugs)
        self.assertEqual(len(market.outcome_labels), 2)

    def test_moneyline_leg_is_orphan_without_composite(self, _mock_translate):
        orphan = Market(
            external_id="leg-tennis-ml",
            title="Roland Garros ATP: Test Player vs Other Player",
            slug="leg-tennis-ml",
            source=Market.Source.POLYMARKET,
            polymarket_raw={
                "sportsMarketType": "moneyline",
                "outcomes": '["Test Player", "Other Player"]',
            },
            polymarket_event_raw=TENNIS_H2H_EVENT,
        )
        self.assertTrue(is_orphan_polymarket_leg(orphan))
        self.assertIsNone(get_composite_redirect_market(orphan))

    def test_moneyline_leg_redirects_after_composite_import(self, _mock_translate):
        normalized = normalize_h2h_match_event(TENNIS_H2H_EVENT)
        import_market_from_normalized(
            normalized,
            raw_market=build_h2h_match_raw(TENNIS_H2H_EVENT, normalized=normalized),
            raw_event=TENNIS_H2H_EVENT,
        )
        orphan = Market(
            external_id="leg-tennis-ml-2",
            title="Roland Garros ATP: Test Player vs Other Player",
            slug="leg-tennis-ml-2",
            source=Market.Source.POLYMARKET,
            polymarket_raw={"sportsMarketType": "moneyline"},
            polymarket_event_raw=TENNIS_H2H_EVENT,
        )
        target = get_composite_redirect_market(orphan)
        self.assertIsNotNone(target)
        self.assertTrue(target.external_id.startswith(H2H_MATCH_EXTERNAL_PREFIX))

    def test_public_listings_include_h2h_match(self, _mock_translate):
        normalized = normalize_h2h_match_event(TENNIS_H2H_EVENT)
        market, _ = import_market_from_normalized(
            normalized,
            raw_market=build_h2h_match_raw(TENNIS_H2H_EVENT, normalized=normalized),
            raw_event=TENNIS_H2H_EVENT,
        )
        listed = filter_markets_by_browse_area(
            markets=get_markets_list(category="sports"),
            category_slug="sports",
            area_slug="tennis",
        )
        self.assertIn(market.pk, [item.pk for item in listed])


@patch("markets.translation_services.translate_market_copy", side_effect=lambda text: text)
class HeadToHeadMatchSyncTests(TestCase):
    @patch("integrations.services.PolymarketClient.fetch_h2h_match_events")
    def test_sync_h2h_match_markets(self, mock_fetch, _mock_translate):
        mock_fetch.return_value = [TENNIS_H2H_EVENT]
        result = sync_h2h_match_markets(limit=5)
        self.assertEqual(len(result["imported"]), 1)
        self.assertEqual(
            result["imported"][0]["market"].external_id,
            f"{H2H_MATCH_EXTERNAL_PREFIX}atp-testplayer-rival-2026-06-02",
        )
