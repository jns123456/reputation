from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from markets.ending_filters import ending_window_hours, normalize_ending_filter
from markets.models import Market
from markets.selectors import get_markets_for_display


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


class EndingSoonFilterTests(TestCase):
    def test_normalize_ending_filter(self):
        self.assertEqual(normalize_ending_filter("24h"), "24h")
        self.assertEqual(normalize_ending_filter("7d"), "7d")
        self.assertEqual(normalize_ending_filter("bogus"), "")
        self.assertEqual(normalize_ending_filter(""), "")

    def test_ending_window_hours(self):
        self.assertEqual(ending_window_hours("24h"), 24)
        self.assertEqual(ending_window_hours("7d"), 168)
        self.assertIsNone(ending_window_hours("bogus"))

    def _market(self, *, slug, close_date, status=Market.Status.OPEN):
        return Market.objects.create(
            external_id=slug,
            title=slug,
            slug=slug,
            source=Market.Source.POLYMARKET,
            status=status,
            close_date=close_date,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
        )

    def test_ending_within_24h_filters_and_orders(self):
        now = timezone.now()
        self._market(slug="ends-soon", close_date=now + timedelta(hours=3))
        self._market(slug="ends-sooner", close_date=now + timedelta(hours=1))
        self._market(slug="ends-later", close_date=now + timedelta(hours=48))
        self._market(slug="already-ended", close_date=now - timedelta(hours=1))
        self._market(slug="no-date", close_date=None)

        results = get_markets_for_display(ending_within_hours=24)

        self.assertEqual([m.slug for m in results], ["ends-sooner", "ends-soon"])

    def test_ending_window_excludes_closed_markets(self):
        now = timezone.now()
        self._market(
            slug="closed-soon",
            close_date=now + timedelta(hours=2),
            status=Market.Status.CLOSED,
        )
        results = get_markets_for_display(ending_within_hours=24)
        self.assertEqual(results, [])

    def test_market_list_view_ending_filter(self):
        now = timezone.now()
        self._market(slug="view-ends-soon", close_date=now + timedelta(hours=2))
        self._market(slug="view-ends-later", close_date=now + timedelta(days=10))

        response = self.client.get(reverse("markets:all"), {"ending": "24h"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_ending"], "24h")
        slugs = [m.slug for m in response.context["markets"]]
        self.assertIn("view-ends-soon", slugs)
        self.assertNotIn("view-ends-later", slugs)
