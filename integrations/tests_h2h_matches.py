from django.contrib.auth import get_user_model
from django.test import TestCase
from unittest.mock import patch

from integrations.polymarket.head_to_head_matches import (
    H2H_MATCH_EXTERNAL_PREFIX,
    build_h2h_match_raw,
    is_h2h_match_event,
    normalize_h2h_match_event,
)
from integrations.services import (
    import_market_from_normalized,
    refresh_h2h_match_market,
    repair_resolved_markets_with_pending_predictions,
)
from markets.models import Market
from predictions.models import Prediction

User = get_user_model()


NBA_H2H_EVENT = {
    "slug": "nba-lal-bos-2026-06-10",
    "title": "Lakers vs. Celtics",
    "endDate": "2026-06-10T02:00:00Z",
    "volume24hr": 8000,
    "tags": [{"slug": "nba", "label": "NBA"}],
    "markets": [
        {
            "id": "nba-ml-1",
            "question": "Lakers vs. Celtics",
            "sportsMarketType": "moneyline",
            "gameStartTime": "2026-06-10T00:00:00Z",
            "outcomes": '["Lakers", "Celtics"]',
            "outcomePrices": '["0.58", "0.42"]',
            "clobTokenIds": '["tok-lal", "tok-bos"]',
            "closed": False,
        },
    ],
}


NBA_H2H_RESOLVED_EVENT = {
    **NBA_H2H_EVENT,
    "markets": [
        {
            **NBA_H2H_EVENT["markets"][0],
            "closed": True,
            "automaticallyResolved": True,
            "umaResolutionStatus": "resolved",
            "outcomePrices": '["1", "0"]',
        },
    ],
}


class H2HMatchNormalizationTests(TestCase):
    def test_is_h2h_match_event_with_closed_moneyline(self):
        self.assertTrue(is_h2h_match_event(NBA_H2H_EVENT))
        self.assertTrue(is_h2h_match_event(NBA_H2H_RESOLVED_EVENT))

    def test_normalize_resolved_h2h_after_moneyline_closed(self):
        normalized = normalize_h2h_match_event(NBA_H2H_RESOLVED_EVENT)
        self.assertIsNotNone(normalized)
        self.assertEqual(normalized["status"], "resolved")
        self.assertEqual(normalized["resolved_outcome"], "Lakers")
        self.assertAlmostEqual(normalized["current_probability"]["Lakers"], 1.0)

    @patch("markets.translation_services.translate_market_copy", side_effect=lambda text: text)
    def test_import_h2h_match_market(self, _mock_translate):
        normalized = normalize_h2h_match_event(NBA_H2H_EVENT)
        raw_market = build_h2h_match_raw(NBA_H2H_EVENT, normalized=normalized)
        market, created = import_market_from_normalized(
            normalized,
            raw_market=raw_market,
            raw_event=NBA_H2H_EVENT,
        )
        self.assertTrue(created)
        self.assertEqual(
            market.external_id,
            f"{H2H_MATCH_EXTERNAL_PREFIX}nba-lal-bos-2026-06-10",
        )
        self.assertEqual(market.outcome_labels, ["Lakers", "Celtics"])


class ResolvedH2HMatchRefreshTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="h2h-refresh-user", password="pass")

    @patch("markets.translation_services.translate_market_copy", side_effect=lambda text: text)
    @patch("integrations.services.PolymarketClient.fetch_event_by_slug")
    def test_refresh_resolved_h2h_scores_pending_forecast(
        self, mock_fetch_event, _mock_translate
    ):
        mock_fetch_event.return_value = NBA_H2H_RESOLVED_EVENT
        normalized = normalize_h2h_match_event(NBA_H2H_EVENT)
        raw_market = build_h2h_match_raw(NBA_H2H_EVENT, normalized=normalized)
        market, _ = import_market_from_normalized(
            normalized,
            raw_market=raw_market,
            raw_event=NBA_H2H_EVENT,
        )
        prediction = Prediction.objects.create(
            user=self.user,
            market=market,
            predicted_outcome="Lakers",
            predicted_direction=Prediction.Direction.YES,
            probability_at_prediction_time=dict(market.current_probability or {}),
        )

        refresh_h2h_match_market(market)
        prediction.refresh_from_db()
        market.refresh_from_db()

        self.assertEqual(market.status, Market.Status.RESOLVED)
        self.assertEqual(market.resolved_outcome, "Lakers")
        self.assertEqual(prediction.status, Prediction.Status.RESOLVED)
        self.assertTrue(prediction.is_correct)

    @patch("markets.translation_services.translate_market_copy", side_effect=lambda text: text)
    @patch("integrations.services.refresh_market_from_polymarket")
    def test_repair_batch_refreshes_stuck_h2h_forecast(self, mock_refresh, _mock_translate):
        def _fake_refresh(m):
            return refresh_h2h_match_market(m)

        mock_refresh.side_effect = _fake_refresh

        normalized = normalize_h2h_match_event(NBA_H2H_EVENT)
        raw_market = build_h2h_match_raw(NBA_H2H_EVENT, normalized=normalized)
        market, _ = import_market_from_normalized(
            normalized,
            raw_market=raw_market,
            raw_event=NBA_H2H_EVENT,
        )
        Prediction.objects.create(
            user=self.user,
            market=market,
            predicted_outcome="Lakers",
            predicted_direction=Prediction.Direction.YES,
            probability_at_prediction_time=dict(market.current_probability or {}),
        )

        with patch(
            "integrations.services.PolymarketClient.fetch_event_by_slug",
            return_value=NBA_H2H_RESOLVED_EVENT,
        ):
            result = repair_resolved_markets_with_pending_predictions()

        market.refresh_from_db()
        prediction = Prediction.objects.get(market=market, user=self.user)

        self.assertTrue(
            result["resolved_predictions"] >= 1 or result["refreshed_markets"] >= 1,
            msg=f"repair should refresh or score: {result}",
        )
        self.assertEqual(market.status, Market.Status.RESOLVED)
        self.assertEqual(prediction.status, Prediction.Status.RESOLVED)
        self.assertTrue(prediction.is_correct)
