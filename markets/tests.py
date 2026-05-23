from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from markets.models import Market


class MarketExpirationCountdownTests(TestCase):
    def test_days_left(self):
        market = Market(
            external_id="exp-1",
            title="Future market",
            slug="future-market",
            status=Market.Status.OPEN,
            close_date=timezone.now() + timedelta(days=30),
        )
        countdown = market.expiration_countdown
        self.assertEqual(countdown["days"], 30)
        self.assertEqual(countdown["text"], "30 days left")
        self.assertEqual(countdown["tone"], "normal")

    def test_urgent_within_week(self):
        market = Market(
            external_id="exp-2",
            title="Soon market",
            slug="soon-market",
            status=Market.Status.OPEN,
            close_date=timezone.now() + timedelta(days=5),
        )
        self.assertEqual(market.expiration_countdown["tone"], "urgent")

    def test_ends_today(self):
        market = Market(
            external_id="exp-3",
            title="Today market",
            slug="today-market",
            status=Market.Status.OPEN,
            close_date=timezone.now(),
        )
        self.assertEqual(market.expiration_countdown["text"], "Ends today")

    def test_resolved_market(self):
        market = Market(
            external_id="exp-4",
            title="Done market",
            slug="done-market",
            status=Market.Status.RESOLVED,
            close_date=timezone.now() - timedelta(days=10),
        )
        self.assertEqual(market.expiration_countdown["text"], "Resolved")

    def test_no_close_date(self):
        market = Market(
            external_id="exp-5",
            title="Open ended",
            slug="open-ended",
            status=Market.Status.OPEN,
        )
        self.assertIsNone(market.expiration_countdown)
