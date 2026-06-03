from django.contrib.auth import get_user_model
from django.test import TestCase
from unittest.mock import patch

from integrations.polymarket.client import (
    build_polymarket_event_raw,
    grouped_outcome_bucket_lost,
    normalize_polymarket_event_record,
)
from integrations.polymarket.constants import MULTI_OUTCOME_EVENT_KIND, POLYMARKET_EVENT_EXTERNAL_PREFIX
from integrations.services import import_market_from_normalized, refresh_polymarket_multi_outcome_market
from markets.models import Market
from predictions.models import Prediction
from predictions.services import resolve_eliminated_outcome_predictions
from reputation.services import get_predicted_outcome_probability

User = get_user_model()


def _player_bucket(player, *, yes_price, closed=False, resolved=False):
    market = {
        "id": f"id-{player.lower().replace(' ', '-')}",
        "question": f"Will {player} win?",
        "outcomes": '["Yes", "No"]',
        "groupItemTitle": player,
        "outcomePrices": f'["{yes_price}", "{1 - yes_price}"]',
        "closed": closed,
    }
    if resolved:
        market["automaticallyResolved"] = True
        market["umaResolutionStatus"] = "resolved"
    return market


FRENCH_OPEN_PARTIAL = {
    "slug": "2026-womens-french-open-winner",
    "title": "2026 Women's French Open Winner",
    "endDate": "2026-06-06T00:00:00Z",
    "markets": [
        _player_bucket("Aryna Sabalenka", yes_price=0.0, closed=True, resolved=True),
        _player_bucket("Iga Swiatek", yes_price=0.22, closed=False),
        _player_bucket("Coco Gauff", yes_price=0.18, closed=False),
    ],
}


class GroupedEliminationTests(TestCase):
    def test_grouped_outcome_bucket_lost_detects_eliminated_player(self):
        sabalenka = FRENCH_OPEN_PARTIAL["markets"][0]
        swiatek = FRENCH_OPEN_PARTIAL["markets"][1]
        self.assertTrue(grouped_outcome_bucket_lost(sabalenka))
        self.assertFalse(grouped_outcome_bucket_lost(swiatek))

    def test_normalize_includes_closed_outcome_prices(self):
        normalized = normalize_polymarket_event_record(FRENCH_OPEN_PARTIAL)
        self.assertEqual(normalized["status"], "open")
        self.assertAlmostEqual(normalized["current_probability"]["Aryna Sabalenka"], 0.0)
        self.assertAlmostEqual(normalized["current_probability"]["Iga Swiatek"], 0.22)

    def test_missing_eliminated_outcome_in_snapshot_reads_as_zero(self):
        prob = get_predicted_outcome_probability(
            "Aryna Sabalenka",
            {"Iga Swiatek": 0.22},
        )
        self.assertEqual(prob, 0.0)

    @patch("markets.translation_services.translate_market_copy", side_effect=lambda text: text)
    def test_resolve_eliminated_outcome_scores_losing_forecast(self, _mock_translate):
        normalized = normalize_polymarket_event_record(FRENCH_OPEN_PARTIAL)
        raw = build_polymarket_event_raw(FRENCH_OPEN_PARTIAL, normalized=normalized)
        market, _ = import_market_from_normalized(
            normalized,
            raw_market=raw,
            raw_event=FRENCH_OPEN_PARTIAL,
        )
        user = User.objects.create_user(username="french-open-user", password="pass")
        prediction = Prediction.objects.create(
            user=user,
            market=market,
            predicted_outcome="Aryna Sabalenka",
            predicted_direction=Prediction.Direction.YES,
            probability_at_prediction_time={"Aryna Sabalenka": 0.34},
        )
        user.profile.refresh_from_db()
        points_before = user.profile.reputation_points

        resolved = resolve_eliminated_outcome_predictions(market, raw_event=FRENCH_OPEN_PARTIAL)
        prediction.refresh_from_db()
        user.profile.refresh_from_db()

        self.assertEqual(len(resolved), 1)
        self.assertEqual(prediction.status, Prediction.Status.RESOLVED)
        self.assertFalse(prediction.is_correct)
        self.assertEqual(user.profile.reputation_points, points_before - 34)

    @patch("markets.translation_services.translate_market_copy", side_effect=lambda text: text)
    @patch("integrations.services.PolymarketClient.fetch_event_by_slug")
    def test_refresh_eliminates_stuck_sabalenka_forecast(self, mock_fetch, _mock_translate):
        mock_fetch.return_value = FRENCH_OPEN_PARTIAL
        normalized = normalize_polymarket_event_record(FRENCH_OPEN_PARTIAL)
        raw = build_polymarket_event_raw(FRENCH_OPEN_PARTIAL, normalized=normalized)
        market, _ = import_market_from_normalized(
            normalized,
            raw_market={**raw, "market_kind": MULTI_OUTCOME_EVENT_KIND},
            raw_event=FRENCH_OPEN_PARTIAL,
        )
        market.external_id = f"{POLYMARKET_EVENT_EXTERNAL_PREFIX}2026-womens-french-open-winner"
        market.polymarket_slug = "2026-womens-french-open-winner"
        market.save(update_fields=["external_id", "polymarket_slug", "updated_at"])

        user = User.objects.create_user(username="french-open-refresh", password="pass")
        prediction = Prediction.objects.create(
            user=user,
            market=market,
            predicted_outcome="Aryna Sabalenka",
            probability_at_prediction_time={"Aryna Sabalenka": 0.34},
        )

        refresh_polymarket_multi_outcome_market(market)
        prediction.refresh_from_db()
        market.refresh_from_db()

        self.assertEqual(market.status, Market.Status.OPEN)
        self.assertAlmostEqual(market.current_probability.get("Aryna Sabalenka", -1), 0.0)
        self.assertEqual(prediction.status, Prediction.Status.RESOLVED)
        self.assertFalse(prediction.is_correct)
