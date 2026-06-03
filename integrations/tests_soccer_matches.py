from django.contrib.auth import get_user_model
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
from integrations.services import (
    import_market_from_normalized,
    refresh_world_cup_match_market,
    repair_resolved_markets_with_pending_predictions,
    sync_world_cup_match_markets,
)
from markets.models import Market
from predictions.models import Prediction

User = get_user_model()


MEXICO_VS_RSA_EVENT = {
    "slug": "fifwc-mex-rsa-2026-06-11",
    "title": "Mexico vs. South Africa",
    "startDate": "2026-04-06T22:38:23Z",
    "endDate": "2026-06-11T21:00:00Z",
    "volume24hr": 21240,
    "tags": [{"slug": "fifa-world-cup", "label": "FIFA World Cup"}],
    "markets": [
        {
            "id": "m1",
            "question": "Will Mexico win on 2026-06-11?",
            "sportsMarketType": "moneyline",
            "gameStartTime": "2026-06-11T19:00:00Z",
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["0.665", "0.335"]',
            "closed": False,
        },
        {
            "id": "m2",
            "question": "Will Mexico vs. South Africa end in a draw?",
            "sportsMarketType": "moneyline",
            "gameStartTime": "2026-06-11T19:00:00Z",
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["0.215", "0.785"]',
            "closed": False,
        },
        {
            "id": "m3",
            "question": "Will South Africa win on 2026-06-11?",
            "sportsMarketType": "moneyline",
            "gameStartTime": "2026-06-11T19:00:00Z",
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["0.125", "0.875"]',
            "closed": False,
        },
    ],
}


COLOMBIA_VS_COSTA_RICA_EVENT = {
    "slug": "fif-col-cri-2026-06-01",
    "title": "Colombia vs Costa Rica",
    "startDate": "2026-05-20T00:11:00Z",
    "endDate": "2026-06-01T23:00:00Z",
    "volume24hr": 12000,
    "tags": [{"slug": "fifa-friendlies", "label": "FIFA Friendlies"}],
    "markets": [
        {
            "id": "col-win",
            "question": "Will Colombia win on 2026-06-01?",
            "sportsMarketType": "moneyline",
            "gameStartTime": "2026-06-01T23:00:00Z",
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["0.86", "0.14"]',
            "clobTokenIds": '["token-col"]',
            "closed": False,
        },
        {
            "id": "draw",
            "question": "Will Colombia vs. Costa Rica end in a draw?",
            "sportsMarketType": "moneyline",
            "gameStartTime": "2026-06-01T23:00:00Z",
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["0.11", "0.89"]',
            "clobTokenIds": '["token-draw"]',
            "closed": False,
        },
        {
            "id": "cri-win",
            "question": "Will Costa Rica win on 2026-06-01?",
            "sportsMarketType": "moneyline",
            "gameStartTime": "2026-06-01T23:00:00Z",
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["0.05", "0.95"]',
            "clobTokenIds": '["token-cri"]',
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
        self.assertTrue(is_world_cup_match_event(COLOMBIA_VS_COSTA_RICA_EVENT))
        self.assertFalse(is_world_cup_match_event({"title": "Mexico vs. South Africa - More Markets", "markets": []}))

    def test_normalize_fifa_friendly_match_event(self):
        normalized = normalize_world_cup_match_event(COLOMBIA_VS_COSTA_RICA_EVENT)
        self.assertIsNotNone(normalized)
        self.assertEqual(normalized["title"], "Colombia vs Costa Rica")
        self.assertEqual(
            [item["label"] for item in normalized["outcomes"]],
            ["Colombia", DRAW_OUTCOME_LABEL, "Costa Rica"],
        )
        self.assertAlmostEqual(normalized["current_probability"]["Colombia"], 0.86)
        self.assertAlmostEqual(normalized["current_probability"][DRAW_OUTCOME_LABEL], 0.11)
        self.assertAlmostEqual(normalized["current_probability"]["Costa Rica"], 0.05)

    def test_normalize_world_cup_match_event(self):
        normalized = normalize_world_cup_match_event(MEXICO_VS_RSA_EVENT)
        self.assertIsNotNone(normalized)
        self.assertEqual(normalized["external_id"], f"{WORLD_CUP_MATCH_EXTERNAL_PREFIX}fifwc-mex-rsa-2026-06-11")
        self.assertEqual([item["label"] for item in normalized["outcomes"]], ["Mexico", DRAW_OUTCOME_LABEL, "South Africa"])
        self.assertAlmostEqual(normalized["current_probability"]["Mexico"], 0.665)
        self.assertAlmostEqual(normalized["current_probability"][DRAW_OUTCOME_LABEL], 0.215)
        self.assertAlmostEqual(normalized["current_probability"]["South Africa"], 0.125)

    def test_normalize_captures_kickoff_and_accepting_orders(self):
        normalized = normalize_world_cup_match_event(MEXICO_VS_RSA_EVENT)
        self.assertTrue(normalized["accepting_orders"])
        self.assertIsNotNone(normalized["game_start_time"])
        self.assertEqual(normalized["game_start_time"].isoformat(), "2026-06-11T19:00:00+00:00")
        self.assertNotEqual(
            normalized["game_start_time"].isoformat(),
            "2026-04-06T22:38:23+00:00",
        )

    def test_normalize_marks_not_accepting_orders_when_source_halts(self):
        event = {
            **MEXICO_VS_RSA_EVENT,
            "markets": [
                {**market, "acceptingOrders": False}
                for market in MEXICO_VS_RSA_EVENT["markets"]
            ],
        }
        normalized = normalize_world_cup_match_event(event)
        self.assertFalse(normalized["accepting_orders"])

    @patch("markets.translation_services.translate_market_copy", side_effect=lambda text: text)
    def test_import_world_cup_match_market(self, _mock_translate):
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

    def test_build_soccer_match_raw_excludes_draw_from_chart_outcomes(self):
        normalized = normalize_world_cup_match_event(COLOMBIA_VS_COSTA_RICA_EVENT)
        raw_market = build_world_cup_match_raw(COLOMBIA_VS_COSTA_RICA_EVENT, normalized=normalized)
        self.assertEqual(
            [item["label"] for item in raw_market["chart_outcomes"]],
            ["Colombia", "Costa Rica"],
        )
        self.assertEqual(raw_market["moneyline_markets"]["Colombia"]["yes_token_id"], "token-col")
        self.assertEqual(raw_market["moneyline_markets"][DRAW_OUTCOME_LABEL]["yes_token_id"], "token-draw")

    def test_ordered_soccer_probability_items_home_draw_away(self):
        from integrations.polymarket.soccer_matches import ordered_soccer_probability_items

        normalized = normalize_world_cup_match_event(COLOMBIA_VS_COSTA_RICA_EVENT)
        raw_market = build_world_cup_match_raw(COLOMBIA_VS_COSTA_RICA_EVENT, normalized=normalized)
        market, _ = import_market_from_normalized(
            normalized,
            raw_market=raw_market,
            raw_event=COLOMBIA_VS_COSTA_RICA_EVENT,
        )
        # Simulate scrambled JSON key order (as seen in some stored records).
        market.current_probability = {
            DRAW_OUTCOME_LABEL: 0.11,
            "Costa Rica": 0.05,
            "Colombia": 0.86,
        }
        self.assertEqual(
            [label for label, _prob in ordered_soccer_probability_items(market)],
            ["Colombia", DRAW_OUTCOME_LABEL, "Costa Rica"],
        )


class SyncWorldCupMatchMarketsTests(TestCase):
    @patch("markets.translation_services.translate_market_copy", side_effect=lambda text: text)
    @patch("integrations.services.PolymarketClient.fetch_soccer_match_events")
    def test_sync_world_cup_match_markets(self, mock_fetch, _mock_translate):
        mock_fetch.return_value = [MEXICO_VS_RSA_EVENT]
        result = sync_world_cup_match_markets(limit=5)
        mock_fetch.assert_called_once_with(limit=5)
        self.assertEqual(len(result["imported"]), 1)
        market = result["imported"][0]["market"]
        self.assertEqual(market.external_id, f"{WORLD_CUP_MATCH_EXTERNAL_PREFIX}fifwc-mex-rsa-2026-06-11")
        self.assertTrue(Market.objects.filter(external_id=market.external_id).exists())

    @patch("integrations.polymarket.client.PolymarketClient.fetch_events_paginated")
    def test_fetch_soccer_match_events_paginates(self, mock_fetch_paginated):
        from integrations.polymarket.client import PolymarketClient

        def make_match(slug):
            event = dict(MEXICO_VS_RSA_EVENT)
            event["slug"] = slug
            event["title"] = f"Team Home vs. Team Away {slug}"
            return event

        matches = [make_match(f"match-{idx}") for idx in range(101)]
        mock_fetch_paginated.return_value = matches

        client = PolymarketClient()
        result = client.fetch_soccer_match_events(tag_slugs=("fifa-world-cup",))
        self.assertEqual(len(result), 101)
        mock_fetch_paginated.assert_called_once()

    @patch("markets.translation_services.translate_market_copy", side_effect=lambda text: text)
    @patch("integrations.services.PolymarketClient.fetch_soccer_match_events")
    def test_sync_includes_fifa_friendlies(self, mock_fetch, _mock_translate):
        mock_fetch.return_value = [COLOMBIA_VS_COSTA_RICA_EVENT]
        result = sync_world_cup_match_markets(limit=5)
        self.assertEqual(len(result["imported"]), 1)
        market = result["imported"][0]["market"]
        self.assertEqual(market.title, "Colombia vs Costa Rica")
        self.assertEqual(market.canonical_category_slug, "sports")


COLOMBIA_VS_COSTA_RICA_RESOLVED_EVENT = {
    **COLOMBIA_VS_COSTA_RICA_EVENT,
    "markets": [
        {
            **COLOMBIA_VS_COSTA_RICA_EVENT["markets"][0],
            "closed": True,
            "automaticallyResolved": True,
            "umaResolutionStatus": "resolved",
            "outcomePrices": '["1", "0"]',
        },
        {
            **COLOMBIA_VS_COSTA_RICA_EVENT["markets"][1],
            "closed": True,
            "outcomePrices": '["0", "1"]',
        },
        {
            **COLOMBIA_VS_COSTA_RICA_EVENT["markets"][2],
            "closed": True,
            "outcomePrices": '["0", "1"]',
        },
    ],
}


class ResolvedSoccerMatchRefreshTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="col-cri-user", password="pass")

    def test_is_soccer_match_event_when_all_moneyline_legs_closed(self):
        self.assertTrue(is_world_cup_match_event(COLOMBIA_VS_COSTA_RICA_RESOLVED_EVENT))

    def test_normalize_resolved_soccer_match_after_all_legs_closed(self):
        normalized = normalize_world_cup_match_event(COLOMBIA_VS_COSTA_RICA_RESOLVED_EVENT)
        self.assertIsNotNone(normalized)
        self.assertEqual(normalized["status"], "resolved")
        self.assertEqual(normalized["resolved_outcome"], "Colombia")
        self.assertAlmostEqual(normalized["current_probability"]["Colombia"], 1.0)

    @patch("markets.translation_services.translate_market_copy", side_effect=lambda text: text)
    @patch("integrations.services.PolymarketClient.fetch_event_by_slug")
    def test_refresh_resolved_soccer_match_scores_pending_forecast(
        self, mock_fetch_event, _mock_translate
    ):
        mock_fetch_event.return_value = COLOMBIA_VS_COSTA_RICA_RESOLVED_EVENT
        normalized = normalize_world_cup_match_event(COLOMBIA_VS_COSTA_RICA_EVENT)
        raw_market = build_world_cup_match_raw(COLOMBIA_VS_COSTA_RICA_EVENT, normalized=normalized)
        market, _ = import_market_from_normalized(
            normalized,
            raw_market=raw_market,
            raw_event=COLOMBIA_VS_COSTA_RICA_EVENT,
        )
        prediction = Prediction.objects.create(
            user=self.user,
            market=market,
            predicted_outcome="Colombia",
            predicted_direction=Prediction.Direction.YES,
            probability_at_prediction_time=dict(market.current_probability or {}),
        )

        refresh_world_cup_match_market(market)
        prediction.refresh_from_db()
        market.refresh_from_db()

        self.assertEqual(market.status, Market.Status.RESOLVED)
        self.assertEqual(market.resolved_outcome, "Colombia")
        self.assertEqual(prediction.status, Prediction.Status.RESOLVED)
        self.assertTrue(prediction.is_correct)

    @patch("markets.translation_services.translate_market_copy", side_effect=lambda text: text)
    @patch("integrations.services.refresh_market_from_polymarket")
    def test_repair_batch_refreshes_stuck_soccer_match_forecast(
        self, mock_refresh, _mock_translate
    ):
        def _fake_refresh(m):
            return refresh_world_cup_match_market(m)

        mock_refresh.side_effect = _fake_refresh

        normalized = normalize_world_cup_match_event(COLOMBIA_VS_COSTA_RICA_EVENT)
        raw_market = build_world_cup_match_raw(COLOMBIA_VS_COSTA_RICA_EVENT, normalized=normalized)
        market, _ = import_market_from_normalized(
            normalized,
            raw_market=raw_market,
            raw_event=COLOMBIA_VS_COSTA_RICA_EVENT,
        )
        prediction = Prediction.objects.create(
            user=self.user,
            market=market,
            predicted_outcome="Colombia",
            predicted_direction=Prediction.Direction.YES,
            probability_at_prediction_time=dict(market.current_probability or {}),
        )
        market.polymarket_event_raw = COLOMBIA_VS_COSTA_RICA_RESOLVED_EVENT
        market.save(update_fields=["polymarket_event_raw", "updated_at"])

        with patch(
            "integrations.services.PolymarketClient.fetch_event_by_slug",
            return_value=COLOMBIA_VS_COSTA_RICA_RESOLVED_EVENT,
        ):
            result = repair_resolved_markets_with_pending_predictions()

        prediction.refresh_from_db()
        market.refresh_from_db()

        self.assertTrue(
            result["resolved_predictions"] >= 1 or result["refreshed_markets"] >= 1,
            msg=f"repair should refresh or score: {result}",
        )
        self.assertEqual(market.status, Market.Status.RESOLVED)
        self.assertEqual(market.resolved_outcome, "Colombia")
        self.assertEqual(prediction.status, Prediction.Status.RESOLVED)
        self.assertTrue(prediction.is_correct)
