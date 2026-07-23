from datetime import timedelta
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from markets.ending_filters import ending_window_hours, normalize_ending_filter
from markets.models import Market
from markets.selectors import get_landing_tape_markets, get_market_categories, get_markets_for_display
from markets.sort_options import SORT_LIQUIDITY


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

    def test_market_list_sports_category_includes_world_cup_matches(self):
        Market.objects.create(
            external_id="wc-match:uruguay-all",
            title="Uruguay vs. Cabo Verde",
            slug="uruguay-vs-cabo-verde-all",
            status=Market.Status.OPEN,
            polymarket_raw={"market_kind": "soccer_match_3way"},
            polymarket_event_raw={"tags": [{"slug": "fifa-world-cup"}]},
        )
        Market.objects.create(
            external_id="nba-all",
            title="NBA champion",
            slug="nba-champion-all",
            status=Market.Status.OPEN,
            polymarket_event_raw={"tags": [{"slug": "nba"}]},
        )

        response = self.client.get(reverse("markets:all"), {"category": "sports"})

        self.assertEqual(response.status_code, 200)
        slugs = [market.slug for market in response.context["markets"]]
        self.assertIn("uruguay-vs-cabo-verde-all", slugs)
        self.assertIn("nba-champion-all", slugs)

    def test_market_list_search_matches_spanish_title(self):
        Market.objects.create(
            external_id="es-title-market",
            title="English placeholder",
            title_es="Uruguay contra Cabo Verde",
            slug="uruguay-es-title",
            status=Market.Status.OPEN,
            polymarket_event_raw={"tags": [{"slug": "soccer"}]},
        )

        response = self.client.get(reverse("markets:all"), {"q": "Uruguay", "status": "open"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual([market.slug for market in response.context["markets"]], ["uruguay-es-title"])

    @override_settings(MARKET_LIST_PAGE_SIZE=2)
    def test_market_list_pagination(self):
        for index in range(3):
            Market.objects.create(
                external_id=f"all-page-{index}",
                title=f"Market page {index}",
                slug=f"market-page-{index}",
                status=Market.Status.OPEN,
                volume_total=float(100 - index),
                polymarket_event_raw={"tags": [{"slug": "soccer"}]},
            )

        response = self.client.get(reverse("markets:all"), {"status": "open"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["page_obj"].has_next)
        self.assertEqual(response.context["market_count"], 3)

        page_two = self.client.get(reverse("markets:all"), {"status": "open", "page": 2})
        self.assertEqual(page_two.status_code, 200)
        self.assertContains(page_two, "Next")

    def test_market_list_defaults_to_open_status(self):
        open_market = Market.objects.create(
            external_id="default-open-market",
            title="Default open market",
            slug="default-open-market",
            status=Market.Status.OPEN,
            polymarket_event_raw={"tags": [{"slug": "soccer"}]},
        )
        Market.objects.create(
            external_id="default-resolved-market",
            title="Default resolved market",
            slug="default-resolved-market",
            status=Market.Status.RESOLVED,
        )

        response = self.client.get(reverse("markets:all"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_status"], Market.Status.OPEN)
        slugs = [market.slug for market in response.context["markets"]]
        self.assertEqual(slugs, [open_market.slug])

    @override_settings(MARKET_LIST_PAGE_SIZE=1)
    def test_market_list_all_statuses_uses_windowed_pagination(self):
        for index, status in enumerate((Market.Status.OPEN, Market.Status.RESOLVED)):
            Market.objects.create(
                external_id=f"all-status-{index}",
                title=f"All status market {index}",
                slug=f"all-status-market-{index}",
                status=status,
                volume_total=float(10 - index),
            )

        response = self.client.get(reverse("markets:all"), {"status": ""})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["page_obj"].paginator.count_is_approximate)
        self.assertTrue(response.context["page_obj"].has_next)

    @override_settings(MARKET_LIST_PAGE_SIZE=1)
    def test_market_list_open_category_uses_windowed_pagination(self):
        """Regression: OPEN + category deep pages must not run COUNT (PREDICTSTAMP-19)."""
        for index in range(2):
            Market.objects.create(
                external_id=f"other-cat-{index}",
                title=f"Other category market {index}",
                slug=f"other-cat-market-{index}",
                status=Market.Status.OPEN,
                category="Other",
                canonical_category_slug="other",
                volume_total=float(10 - index),
                polymarket_event_raw={"tags": [{"slug": "other"}]},
            )

        response = self.client.get(
            reverse("markets:all"),
            {"category": "other", "status": "open", "page": "2"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["page_obj"].paginator.count_is_approximate)

    def test_liquidity_sort_uses_single_denormalized_query(self):
        for index, liquidity in enumerate((100, 900, 300)):
            Market.objects.create(
                external_id=f"liq-sort-{index}",
                title=f"Liquidity market {index}",
                slug=f"liquidity-market-{index}",
                status=Market.Status.OPEN,
                liquidity_total=float(liquidity),
                volume_total=float(index),
                polymarket_raw={"liquidityNum": 1},
            )

        with self.assertNumQueries(1):
            markets = get_markets_for_display(sort=SORT_LIQUIDITY, limit=3)

        self.assertEqual(
            [market.slug for market in markets],
            ["liquidity-market-1", "liquidity-market-2", "liquidity-market-0"],
        )


class MarketApiTests(TestCase):
    def setUp(self):
        self.market = Market.objects.create(
            external_id="api-raw",
            title="API market",
            slug="api-market",
            status=Market.Status.OPEN,
            polymarket_raw={"large": "payload"},
            polymarket_event_raw={"event": "payload"},
        )

    def test_detail_omits_raw_payload_by_default(self):
        response = self.client.get(reverse("market-detail", kwargs={"slug": self.market.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("polymarket_raw", response.json())
        self.assertNotIn("polymarket_event_raw", response.json())

    def test_detail_rejects_include_raw_for_anonymous(self):
        response = self.client.get(
            reverse("market-detail", kwargs={"slug": self.market.slug}),
            {"include_raw": "1"},
        )

        self.assertEqual(response.status_code, 403)

    def test_detail_includes_raw_payload_for_staff(self):
        from django.contrib.auth import get_user_model
        from django.utils import timezone

        staff = get_user_model().objects.create_user(
            username="apistaff",
            email="apistaff@example.com",
            password="testpass123",
            is_staff=True,
            email_verified_at=timezone.now(),
            onboarding_completed=True,
        )
        self.client.force_login(staff)
        response = self.client.get(
            reverse("market-detail", kwargs={"slug": self.market.slug}),
            {"include_raw": "1"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["polymarket_raw"], {"large": "payload"})

    def test_list_defaults_to_open_markets(self):
        open_market = Market.objects.create(
            external_id="api-open-default",
            title="Open default market",
            slug="api-open-default",
            status=Market.Status.OPEN,
            accepting_orders=True,
            close_date=timezone.now() + timedelta(days=3),
        )
        Market.objects.create(
            external_id="api-resolved-default",
            title="Resolved default market",
            slug="api-resolved-default",
            status=Market.Status.RESOLVED,
        )

        response = self.client.get(reverse("market-list"))

        self.assertEqual(response.status_code, 200)
        slugs = [row["slug"] for row in response.json()["results"]]
        self.assertIn(open_market.slug, slugs)
        self.assertNotIn("api-resolved-default", slugs)

    def test_list_all_statuses_skips_full_table_count(self):
        for index, status in enumerate((Market.Status.OPEN, Market.Status.RESOLVED)):
            Market.objects.create(
                external_id=f"api-all-status-{index}",
                title=f"API all status {index}",
                slug=f"api-all-status-{index}",
                status=status,
            )

        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(reverse("market-list"), {"status": ""})

        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json()["results"]), 2)
        self.assertFalse(
            any("COUNT(*)" in query["sql"] for query in ctx.captured_queries),
            msg="all-status market API list must not COUNT the full table",
        )


class MarketListPaginationTransientDbTests(SimpleTestCase):
    @patch("markets.pagination.list")
    def test_windowed_pagination_retries_transient_ssl_eof(self, mock_list):
        from unittest.mock import MagicMock

        from django.db import OperationalError

        from markets.pagination import paginate_queryset_windowed

        mock_list.side_effect = [
            OperationalError(
                "consuming input failed: SSL error: unexpected eof while reading"
            ),
            ["market"],
        ]
        page = paginate_queryset_windowed(MagicMock(), page=1, per_page=20)
        self.assertEqual(list(page), ["market"])
        self.assertEqual(mock_list.call_count, 2)


class LandingTapeSelectorTests(TestCase):
    def _forecastable_market(self, *, slug, title, image_url=""):
        return Market.objects.create(
            external_id=f"tape-{slug}",
            title=title,
            slug=slug,
            status=Market.Status.OPEN,
            accepting_orders=True,
            close_date=timezone.now() + timedelta(days=7),
            card_image_url=image_url,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )

    def test_returns_only_markets_with_images(self):
        with_image = self._forecastable_market(
            slug="tape-with-image",
            title="Election winner",
            image_url="https://example.com/election.png",
        )
        self._forecastable_market(
            slug="tape-no-image",
            title="No image market",
        )

        results = get_landing_tape_markets(limit=10)

        self.assertEqual([market.pk for market in results], [with_image.pk])

    def test_excludes_non_forecastable_markets(self):
        self._forecastable_market(
            slug="tape-closed",
            title="Closed market",
            image_url="https://example.com/closed.png",
        )
        Market.objects.filter(slug="tape-closed").update(
            status=Market.Status.CLOSED,
            accepting_orders=False,
        )

        self.assertEqual(get_landing_tape_markets(limit=10), [])
