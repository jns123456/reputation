"""Tests for Formula 1 race forecast kickoff gating."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from integrations.polymarket.client import normalize_polymarket_event_record
from integrations.polymarket.f1_markets import (
    f1_race_start_from_market,
    f1_race_start_time,
    is_f1_race_event,
    is_f1_race_market,
)
from integrations.services import import_market_from_normalized
from predictions.forms import ForecastForm
from predictions.services import create_prediction


BRITISH_GP_EVENT = {
    "slug": "f1-british-gp-2026-driver-winner",
    "title": "British Grand Prix: Driver Winner",
    "tags": [
        {"slug": "formula1"},
        {"slug": "f1"},
        {"slug": "sports"},
        {"slug": "grand-prix"},
        {"slug": "games"},
    ],
    "startDate": "2026-06-06T11:33:51.540655Z",
    "endDate": "2026-07-12T14:00:00Z",
    "markets": [
        {
            "groupItemTitle": "Max Verstappen",
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["0.40", "0.60"]',
            "closed": False,
            "acceptingOrders": True,
            "gameStartTime": "2026-07-05 14:00:00+00",
            "endDate": "2026-07-12T14:00:00Z",
        },
        {
            "groupItemTitle": "Lando Norris",
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["0.35", "0.65"]',
            "closed": False,
            "acceptingOrders": True,
            "gameStartTime": "2026-07-05 14:00:00+00",
            "endDate": "2026-07-12T14:00:00Z",
        },
    ],
}

F1_DRIVERS_CHAMPION_EVENT = {
    "slug": "f1-drivers-champion-2026",
    "title": "F1 Drivers' Champion",
    "tags": [{"slug": "sports"}, {"slug": "formula1"}, {"slug": "f1"}],
    "startDate": "2025-12-09T00:55:47.605573Z",
    "endDate": "2026-12-06T00:00:00Z",
    "markets": [
        {
            "groupItemTitle": "Max Verstappen",
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["0.55", "0.45"]',
            "closed": False,
            "acceptingOrders": True,
            "endDate": "2026-12-06T00:00:00Z",
        },
    ],
}


class F1RaceDetectionTests(TestCase):
    def test_grand_prix_event_detected_as_f1_race(self):
        self.assertTrue(is_f1_race_event(BRITISH_GP_EVENT))

    def test_season_futures_are_not_f1_race_events(self):
        self.assertFalse(is_f1_race_event(F1_DRIVERS_CHAMPION_EVENT))


class F1RaceStartTimeTests(TestCase):
    def test_race_start_uses_event_end_date_not_submarket_listing_time(self):
        normalized = normalize_polymarket_event_record(
            BRITISH_GP_EVENT,
            default_category="Sports",
            require_open=False,
        )
        self.assertIsNotNone(normalized)
        self.assertEqual(
            normalized["game_start_time"].isoformat(),
            "2026-07-12T14:00:00+00:00",
        )
        self.assertEqual(
            normalized["close_date"].isoformat(),
            "2026-07-12T14:00:00+00:00",
        )

    def test_f1_race_start_time_helper_prefers_close_date(self):
        from datetime import datetime, timezone as dt_timezone

        close = datetime(2026, 7, 12, 14, tzinfo=dt_timezone.utc)
        start = f1_race_start_time(BRITISH_GP_EVENT, close_date=close)
        self.assertEqual(start, close)


class F1RaceForecastGatingTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.user = User.objects.create_user(username="f1-user", password="pass")

    def _import_gp_market(self, *, game_start_time=...):
        normalized = normalize_polymarket_event_record(
            BRITISH_GP_EVENT,
            default_category="Sports",
            require_open=False,
        )
        if game_start_time is not ...:
            normalized["game_start_time"] = game_start_time
        market, _created = import_market_from_normalized(
            normalized,
            raw_market={"market_kind": "multi_outcome_event"},
            raw_event=BRITISH_GP_EVENT,
        )
        return market

    def test_f1_race_import_sets_game_start_time(self):
        market = self._import_gp_market()
        self.assertTrue(is_f1_race_market(market))
        self.assertEqual(
            market.game_start_time.isoformat(),
            "2026-07-12T14:00:00+00:00",
        )

    def test_f1_race_blocks_forecasts_after_race_start(self):
        now = timezone.now()
        market = self._import_gp_market(game_start_time=now - timedelta(minutes=5))
        market.close_date = now + timedelta(hours=2)
        market.save(update_fields=["close_date"])

        self.assertTrue(market.is_in_play)
        self.assertFalse(market.is_forecastable)

        with self.assertRaises(ValueError) as ctx:
            create_prediction(
                user=self.user,
                market=market,
                predicted_outcome="Max Verstappen",
            )
        self.assertIn("already started", str(ctx.exception))

    def test_f1_race_allows_forecasts_before_race_start(self):
        now = timezone.now()
        market = self._import_gp_market(game_start_time=now + timedelta(hours=2))

        self.assertFalse(market.is_in_play)
        self.assertTrue(market.is_forecastable)

        prediction = create_prediction(
            user=self.user,
            market=market,
            predicted_outcome="Max Verstappen",
        )
        self.assertEqual(prediction.predicted_outcome, "Max Verstappen")

    def test_f1_race_runtime_backstop_when_game_start_time_missing(self):
        now = timezone.now()
        market = self._import_gp_market(game_start_time=None)
        market.game_start_time = None
        market.close_date = now - timedelta(minutes=5)
        market.save(update_fields=["game_start_time", "close_date"])

        self.assertEqual(f1_race_start_from_market(market), market.close_date)
        self.assertTrue(market.is_in_play)
        self.assertFalse(market.is_forecastable)

        form = ForecastForm(data={"predicted_outcome": "Max Verstappen"}, market=market)
        self.assertFalse(form.is_valid())
