from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from markets.ending_filters import ending_window_hours, normalize_ending_filter
from markets.models import Market
from markets.selectors import get_market_categories, get_markets_for_display


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

    def test_open_display_excludes_non_forecastable_open_markets(self):
        now = timezone.now()
        self._market(slug="fresh-open", close_date=now + timedelta(hours=2))
        self._market(slug="expired-open", close_date=now - timedelta(minutes=5))
        in_play = self._market(slug="in-play-open", close_date=now + timedelta(hours=2))
        in_play.game_start_time = now - timedelta(minutes=5)
        in_play.save(update_fields=["game_start_time"])
        halted = self._market(slug="halted-open", close_date=now + timedelta(hours=2))
        halted.accepting_orders = False
        halted.save(update_fields=["accepting_orders"])

        results = get_markets_for_display(status=Market.Status.OPEN)

        self.assertEqual({market.slug for market in results}, {"fresh-open"})

    def test_ending_within_24h_excludes_non_forecastable(self):
        now = timezone.now()
        self._market(slug="forecastable-soon", close_date=now + timedelta(hours=2))
        in_play = self._market(slug="in-play-ending-soon", close_date=now + timedelta(hours=3))
        in_play.game_start_time = now - timedelta(minutes=5)
        in_play.save(update_fields=["game_start_time"])

        results = get_markets_for_display(ending_within_hours=24)

        self.assertEqual([m.slug for m in results], ["forecastable-soon"])

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


class MarketCategoryFilterTests(TestCase):
    def test_market_categories_are_canonical(self):
        Market.objects.create(
            external_id="raw-outcome-category",
            title="Raw outcome category",
            slug="raw-outcome-category",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            category="Draw (Team A vs. Team B)",
            canonical_category_slug="sports",
        )

        categories = get_market_categories()

        self.assertLessEqual(len(categories), 10)
        self.assertIn("sports", [category.slug for category in categories])
        self.assertNotIn("Draw (Team A vs. Team B)", [category.name for category in categories])

    def test_market_list_filters_by_canonical_category_slug(self):
        sports_market = Market.objects.create(
            external_id="sports-market",
            title="Sports market",
            slug="sports-market",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            category="Sports",
        )
        Market.objects.filter(pk=sports_market.pk).update(
            category="Draw (Team A vs. Team B)",
            canonical_category_slug="sports",
        )
        Market.objects.create(
            external_id="politics-market",
            title="Politics market",
            slug="politics-market",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            category="Politics",
        )

        response = self.client.get(reverse("markets:all"), {"category": "sports"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_category"], "sports")
        slugs = [market.slug for market in response.context["markets"]]
        self.assertIn("sports-market", slugs)
        self.assertNotIn("politics-market", slugs)

    def test_market_list_accepts_legacy_category_name(self):
        Market.objects.create(
            external_id="legacy-sports-market",
            title="Legacy sports market",
            slug="legacy-sports-market",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            category="Sports",
        )

        response = self.client.get(reverse("markets:all"), {"category": "Sports"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_category"], "sports")
        self.assertEqual([market.slug for market in response.context["markets"]], ["legacy-sports-market"])
