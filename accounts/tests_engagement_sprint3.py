"""Tests for Sprint 3/4 engagement features.

Covers: hot ranking, feed sorts + pagination, resolving-soon reminders,
levels + achievements, @mention linkify, web push, and onboarding activation.
"""

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.achievement_services import evaluate_achievements, get_level_progress
from accounts.models import (
    Notification,
    NotificationPreference,
    PushSubscription,
    UserAchievement,
    UserFollow,
)
from accounts.notification_services import notify_market_resolving
from accounts.push_services import (
    get_vapid_public_key,
    is_enabled,
    save_subscription,
    send_push_to_user,
)
from accounts.templatetags.mention_tags import linkify_mentions
from conftest import create_market, create_user
from dashboard.forecasts_services import build_forecasts_feed
from dashboard.ranking import hot_score
from markets.models import Market
from markets.selectors import get_markets_resolving_soon
from predictions.models import Prediction
from pulse.models import Post
from pulse.selectors import build_pulse_feed


def _make_prediction(user, market, **kwargs):
    return Prediction.objects.create(
        user=user,
        market=market,
        predicted_outcome=kwargs.pop("predicted_outcome", "Yes"),
        probability_at_prediction_time={"Yes": 0.3, "No": 0.7},
        **kwargs,
    )


class HotScoreTests(TestCase):
    def test_more_points_ranks_higher_at_same_time(self):
        now = timezone.now()
        self.assertGreater(
            hot_score(points=100, created_at=now),
            hot_score(points=1, created_at=now),
        )

    def test_newer_ranks_higher_at_same_points(self):
        older = timezone.now() - timedelta(hours=10)
        newer = timezone.now()
        self.assertGreater(
            hot_score(points=10, created_at=newer),
            hot_score(points=10, created_at=older),
        )

    def test_engagement_counts_toward_score(self):
        now = timezone.now()
        self.assertGreater(
            hot_score(points=5, created_at=now, engagement=50),
            hot_score(points=5, created_at=now, engagement=0),
        )


class ForecastsFeedSortTests(TestCase):
    def setUp(self):
        self.viewer = create_user("viewer")
        self.author_a = create_user("author_a")
        self.author_b = create_user("author_b")
        self.market = create_market()

    def test_recent_pagination_has_more(self):
        for author in (self.author_a, self.author_b):
            _make_prediction(author, self.market)
        items, has_more = build_forecasts_feed(
            user=self.viewer, sort="recent", page=1, page_size=1
        )
        self.assertEqual(len(items), 1)
        self.assertTrue(has_more)

        items2, has_more2 = build_forecasts_feed(
            user=self.viewer, sort="recent", page=2, page_size=1
        )
        self.assertEqual(len(items2), 1)
        self.assertFalse(has_more2)

    def test_following_feed_empty_without_follows(self):
        _make_prediction(self.author_a, self.market)
        items, has_more = build_forecasts_feed(user=self.viewer, sort="following")
        self.assertEqual(items, [])
        self.assertFalse(has_more)

    def test_following_feed_returns_followed_authors(self):
        _make_prediction(self.author_a, self.market)
        UserFollow.objects.create(follower=self.viewer, following=self.author_a)
        items, _has_more = build_forecasts_feed(user=self.viewer, sort="following")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["prediction"].user_id, self.author_a.id)

    def test_hot_feed_returns_items_without_pagination(self):
        _make_prediction(self.author_a, self.market)
        items, has_more = build_forecasts_feed(user=self.viewer, sort="hot")
        self.assertEqual(len(items), 1)
        self.assertFalse(has_more)


class ForumFeedSortTests(TestCase):
    def setUp(self):
        self.viewer = create_user("viewer")
        self.author = create_user("poster")

    def test_recent_pagination(self):
        Post.objects.create(user=self.author, body="one")
        Post.objects.create(user=self.author, body="two")
        items, has_more = build_pulse_feed(user=self.viewer, sort="recent", page=1, page_size=1)
        self.assertEqual(len(items), 1)
        self.assertTrue(has_more)

    def test_hot_sort_runs(self):
        Post.objects.create(user=self.author, body="hot", popularity_score=10)
        items, has_more = build_pulse_feed(user=self.viewer, sort="hot")
        self.assertEqual(len(items), 1)
        self.assertFalse(has_more)


class ResolvingSoonTests(TestCase):
    def setUp(self):
        self.user = create_user("forecaster")

    def test_selector_returns_only_imminent_open_markets(self):
        now = timezone.now()
        soon = create_market(
            external_id="m-soon", slug="m-soon", title="Soon",
            close_date=now + timedelta(hours=12),
        )
        create_market(
            external_id="m-far", slug="m-far", title="Far",
            close_date=now + timedelta(days=10),
        )
        create_market(
            external_id="m-closed", slug="m-closed", title="Closed",
            status=Market.Status.CLOSED, close_date=now + timedelta(hours=5),
        )
        result = get_markets_resolving_soon(within_hours=72, limit=10)
        slugs = {m.slug for m in result}
        self.assertIn("m-soon", slugs)
        self.assertNotIn("m-far", slugs)
        self.assertNotIn("m-closed", slugs)

    def test_notify_market_resolving_is_idempotent(self):
        market = create_market(
            external_id="m-x", slug="m-x",
            close_date=timezone.now() + timedelta(hours=6),
        )
        _make_prediction(self.user, market)
        first = notify_market_resolving(market=market)
        self.assertEqual(len(first), 1)
        second = notify_market_resolving(market=market)
        self.assertEqual(second, [])
        self.assertEqual(
            Notification.objects.filter(
                notification_type=Notification.NotificationType.MARKET_RESOLVING
            ).count(),
            1,
        )

    def test_no_reminder_without_open_predictions(self):
        market = create_market(
            external_id="m-y", slug="m-y",
            close_date=timezone.now() + timedelta(hours=6),
        )
        self.assertEqual(notify_market_resolving(market=market), [])


class LevelTests(TestCase):
    def test_rookie_floor(self):
        level = get_level_progress(0)
        self.assertEqual(level["level"], 1)
        self.assertFalse(level["is_max"])

    def test_negative_points_clamp_to_rookie(self):
        level = get_level_progress(-100)
        self.assertEqual(level["level"], 1)
        self.assertEqual(level["progress_pct"], 0)

    def test_max_level(self):
        level = get_level_progress(99999)
        self.assertTrue(level["is_max"])
        self.assertIsNone(level["next_threshold"])
        self.assertEqual(level["progress_pct"], 100)

    def test_progress_between_levels(self):
        # Apprentice floor 50, Analyst 150 -> 100 points = 50% of the way.
        level = get_level_progress(100)
        self.assertEqual(level["progress_pct"], 50)


class AchievementTests(TestCase):
    def setUp(self):
        self.user = create_user("achiever")

    def test_first_forecast_awarded(self):
        self.user.profile.prediction_count = 1
        self.user.profile.save()
        new = evaluate_achievements(self.user)
        self.assertIn("first_forecast", new)
        self.assertTrue(
            UserAchievement.objects.filter(user=self.user, code="first_forecast").exists()
        )

    def test_idempotent(self):
        self.user.profile.prediction_count = 1
        self.user.profile.save()
        evaluate_achievements(self.user)
        again = evaluate_achievements(self.user)
        self.assertNotIn("first_forecast", again)
        self.assertEqual(UserAchievement.objects.filter(user=self.user).count(), 1)

    def test_no_award_when_unmet(self):
        new = evaluate_achievements(self.user)
        self.assertEqual(new, [])


class LinkifyMentionsTests(TestCase):
    def setUp(self):
        self.alice = create_user("alice")

    def test_links_existing_user(self):
        html = linkify_mentions("hi @alice")
        self.assertIn(reverse("accounts:profile", kwargs={"username": "alice"}), html)
        self.assertIn("@alice", html)

    def test_unknown_user_not_linked(self):
        html = linkify_mentions("hi @ghost")
        self.assertNotIn("<a", html)

    def test_escapes_html(self):
        html = linkify_mentions("<script>alert(1)</script> @alice")
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_empty(self):
        self.assertEqual(linkify_mentions(""), "")


class VapidPublicKeyTests(TestCase):
    @override_settings(VAPID_PUBLIC_KEY="Application Server Key = abc123")
    def test_strips_cli_prefix(self):
        self.assertEqual(get_vapid_public_key(), "abc123")

    @override_settings(VAPID_PUBLIC_KEY="  raw-key  ")
    def test_strips_whitespace(self):
        self.assertEqual(get_vapid_public_key(), "raw-key")


class PushSubscriptionServiceTests(TestCase):
    def setUp(self):
        self.user = create_user("pushuser")
        self.sub_payload = {
            "endpoint": "https://push.example.com/abc",
            "keys": {"p256dh": "key123", "auth": "auth123"},
        }

    def test_save_subscription(self):
        sub = save_subscription(user=self.user, subscription=self.sub_payload)
        self.assertEqual(sub.endpoint, "https://push.example.com/abc")
        self.assertEqual(PushSubscription.objects.filter(user=self.user).count(), 1)

    def test_save_subscription_invalid(self):
        with self.assertRaises(ValueError):
            save_subscription(user=self.user, subscription={"endpoint": ""})

    def test_send_disabled_is_noop(self):
        save_subscription(user=self.user, subscription=self.sub_payload)
        # WEBPUSH_ENABLED defaults False in tests.
        self.assertFalse(is_enabled())
        self.assertEqual(
            send_push_to_user(user=self.user, title="x", body="y"), 0
        )

    @override_settings(
        WEBPUSH_ENABLED=True,
        VAPID_PRIVATE_KEY="x",
        VAPID_PUBLIC_KEY="y",
        VAPID_CLAIMS_EMAIL="mailto:a@b.c",
    )
    def test_send_respects_preference(self):
        save_subscription(user=self.user, subscription=self.sub_payload)
        pref = NotificationPreference.objects.get(user=self.user)
        pref.notify_push = False
        pref.save()
        self.assertEqual(send_push_to_user(user=self.user, title="x", body="y"), 0)

    @override_settings(
        WEBPUSH_ENABLED=True,
        VAPID_PRIVATE_KEY="x",
        VAPID_PUBLIC_KEY="y",
        VAPID_CLAIMS_EMAIL="mailto:a@b.c",
    )
    @patch("accounts.push_services._send_one", return_value=True)
    def test_send_fans_out(self, mock_send):
        save_subscription(user=self.user, subscription=self.sub_payload)
        sent = send_push_to_user(user=self.user, title="x", body="y")
        self.assertEqual(sent, 1)
        mock_send.assert_called_once()


class PushEndpointTests(TestCase):
    def setUp(self):
        self.user = create_user("endpointuser")

    def test_vapid_key_endpoint_reports_disabled_by_default(self):
        resp = self.client.get(reverse("accounts:push_vapid_key"))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()["enabled"])

    def test_subscribe_requires_login(self):
        resp = self.client.post(
            reverse("accounts:push_subscribe"),
            data="{}",
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 302)

    def test_subscribe_disabled_returns_503(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            reverse("accounts:push_subscribe"),
            data="{}",
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 503)


class OnboardingViewTests(TestCase):
    def setUp(self):
        self.user = create_user("newbie")

    def test_new_user_sees_onboarding(self):
        # Onboarding (welcome) runs after profile setup completes.
        self.user.onboarding_completed = True
        self.user.save(update_fields=["onboarding_completed"])
        self.client.force_login(self.user)
        resp = self.client.get(reverse("accounts:onboarding"))
        self.assertEqual(resp.status_code, 200)

    def test_user_with_predictions_redirected(self):
        self.user.onboarding_completed = True
        self.user.profile.prediction_count = 3
        self.user.profile.save()
        self.user.save(update_fields=["onboarding_completed"])
        self.client.force_login(self.user)
        resp = self.client.get(reverse("accounts:onboarding"))
        self.assertEqual(resp.status_code, 302)


class FeedPageRenderTests(TestCase):
    """Guard template rendering for the refactored feed pages + sorts."""

    def setUp(self):
        self.user = create_user("reader")
        self.user.onboarding_completed = True
        self.user.save(update_fields=["onboarding_completed"])
        self.author = create_user("writer")
        self.author.onboarding_completed = True
        self.author.save(update_fields=["onboarding_completed"])
        self.market = create_market(
            close_date=timezone.now() + timedelta(hours=10),
        )
        _make_prediction(self.author, self.market)
        Post.objects.create(user=self.author, body="hello forum")
        self.client.force_login(self.user)

    def test_forecasts_page_renders_all_sorts(self):
        for sort in ("recent", "hot", "following"):
            resp = self.client.get(reverse("dashboard:forecasts"), {"sort": sort})
            self.assertEqual(resp.status_code, 200, sort)

    def test_forecasts_feed_partial_pagination(self):
        resp = self.client.get(
            reverse("dashboard:forecasts_feed"), {"sort": "recent", "page": 2}
        )
        self.assertEqual(resp.status_code, 200)

    def test_forum_page_renders_all_sorts(self):
        for sort in ("recent", "hot", "following"):
            resp = self.client.get(reverse("forum:feed"), {"sort": sort})
            self.assertEqual(resp.status_code, 200, sort)

    def test_resolving_soon_strip_present(self):
        resp = self.client.get(reverse("dashboard:forecasts"))
        self.assertContains(resp, "Resolving soon")


class ServiceWorkerTests(TestCase):
    def test_service_worker_served_at_root(self):
        resp = self.client.get("/sw.js")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/javascript", resp["Content-Type"])
        self.assertEqual(resp["Service-Worker-Allowed"], "/")

    def test_manifest_served(self):
        resp = self.client.get("/manifest.webmanifest")
        self.assertEqual(resp.status_code, 200)
