"""Tests for universal event-start forecast gating."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from integrations.polymarket.event_start import (
    grouped_event_start_time,
    resolve_import_game_start_time,
    resolve_market_event_start_time,
)
from integrations.services import import_market_from_normalized
from markets.models import Market
from predictions.services import create_prediction


DEBATE_EVENT = {
    "slug": "presidential-debate-sept-2026",
    "title": "Who wins the September 2026 presidential debate?",
    "tags": [{"slug": "politics"}, {"slug": "debates"}],
    "gameStartTime": "2026-09-15T01:00:00Z",
    "endDate": "2026-09-15T03:00:00Z",
    "markets": [
        {
            "groupItemTitle": "Candidate A",
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["0.55", "0.45"]',
            "closed": False,
            "acceptingOrders": True,
            "endDate": "2026-09-15T03:00:00Z",
        },
    ],
}


class EventStartImportTests(TestCase):
    def test_grouped_event_uses_event_game_start_time(self):
        from datetime import datetime, timezone as dt_timezone

        close = datetime(2026, 9, 15, 3, tzinfo=dt_timezone.utc)
        start = grouped_event_start_time(
            DEBATE_EVENT,
            close_date=close,
            grouped_markets=DEBATE_EVENT["markets"],
        )
        self.assertEqual(start.isoformat(), "2026-09-15T01:00:00+00:00")

    def test_import_persists_close_date_when_start_missing(self):
        data = {
            "external_id": "evt-universal-start",
            "title": "Will something happen?",
            "source": "polymarket",
            "status": "open",
            "outcomes": [{"label": "Yes"}, {"label": "No"}],
            "current_probability": {"Yes": 0.5, "No": 0.5},
            "close_date": timezone.now() + timedelta(days=3),
            "accepting_orders": True,
        }
        market, _created = import_market_from_normalized(data)
        self.assertEqual(market.game_start_time, market.close_date)


class UniversalEventStartGatingTests(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.user = User.objects.create_user(username="event-start-user", password="pass")

    def test_blocks_forecast_after_event_start_for_any_market(self):
        now = timezone.now()
        market = Market.objects.create(
            external_id="universal-in-play",
            title="Any scheduled event",
            slug="universal-in-play",
            status=Market.Status.OPEN,
            close_date=now + timedelta(hours=4),
            game_start_time=now - timedelta(minutes=5),
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )

        self.assertTrue(market.is_in_play)
        self.assertFalse(market.is_forecastable)

        with self.assertRaises(ValueError) as ctx:
            create_prediction(user=self.user, market=market, predicted_outcome="Yes")
        self.assertIn("already started", str(ctx.exception))

    def test_runtime_backstop_uses_close_date_when_start_column_missing(self):
        now = timezone.now()
        market = Market.objects.create(
            external_id="universal-close-backstop",
            title="Event with close only",
            slug="universal-close-backstop",
            status=Market.Status.OPEN,
            close_date=now - timedelta(minutes=3),
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )

        self.assertEqual(resolve_market_event_start_time(market), market.close_date)
        self.assertTrue(market.is_in_play)
        self.assertFalse(market.is_forecastable)

    def test_allows_forecast_before_event_start(self):
        now = timezone.now()
        market = Market.objects.create(
            external_id="universal-before-start",
            title="Future event",
            slug="universal-before-start",
            status=Market.Status.OPEN,
            close_date=now + timedelta(days=2),
            game_start_time=now + timedelta(hours=6),
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )

        self.assertFalse(market.is_in_play)
        self.assertTrue(market.is_forecastable)

    def test_resolve_import_game_start_time_falls_back_to_close_date(self):
        close = timezone.now() + timedelta(days=1)
        resolved = resolve_import_game_start_time({"close_date": close})
        self.assertEqual(resolved, close)
