"""Topic follows, market watches, and For You feed personalization."""

from django.test import TestCase
from django.urls import reverse

from accounts.follow_services import toggle_market_watch, toggle_topic_follow
from accounts.models import MarketWatch, TopicFollow
from conftest import create_market, create_user


class TopicFollowTests(TestCase):
    def setUp(self):
        self.user = create_user("topicuser")

    def test_toggle_topic_follow(self):
        self.assertTrue(toggle_topic_follow(user=self.user, category_slug="sports"))
        self.assertTrue(
            TopicFollow.objects.filter(user=self.user, category_slug="sports").exists()
        )
        self.assertFalse(toggle_topic_follow(user=self.user, category_slug="sports"))
        self.assertFalse(TopicFollow.objects.filter(user=self.user).exists())

    def test_unknown_topic_rejected(self):
        from django.core.exceptions import ValidationError

        with self.assertRaises(ValidationError):
            toggle_topic_follow(user=self.user, category_slug="not-a-topic")

    def test_toggle_endpoint(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("accounts:topic_follow_toggle"),
            {"category_slug": "sports"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(TopicFollow.objects.filter(user=self.user).exists())


class MarketWatchTests(TestCase):
    def setUp(self):
        self.user = create_user("watchuser")
        self.market = create_market(external_id="watch-m", slug="watch-m")

    def test_toggle_market_watch(self):
        self.assertTrue(toggle_market_watch(user=self.user, market=self.market))
        self.assertTrue(
            MarketWatch.objects.filter(user=self.user, market=self.market).exists()
        )
        self.assertFalse(toggle_market_watch(user=self.user, market=self.market))
        self.assertFalse(MarketWatch.objects.filter(user=self.user).exists())

    def test_watchers_receive_market_resolving_notification(self):
        from accounts.models import Notification
        from accounts.notification_services import notify_market_resolving

        toggle_market_watch(user=self.user, market=self.market)
        created = notify_market_resolving(market=self.market)
        self.assertEqual(len(created), 1)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.user,
                notification_type=Notification.NotificationType.MARKET_RESOLVING,
                market=self.market,
            ).exists()
        )


class ForYouFeedTests(TestCase):
    def setUp(self):
        self.user = create_user("foryouuser")

    def test_for_you_page_renders_for_authenticated_user(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard:forecasts"), {"sort": "for_you"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_sort"], "for_you")

    def test_anonymous_for_you_falls_back_to_hot(self):
        response = self.client.get(reverse("dashboard:forecasts"), {"sort": "for_you"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_sort"], "hot")

    def test_personalize_feed_caps_items_per_author(self):
        from datetime import datetime, timezone as dt_timezone

        from dashboard.personalization import personalize_feed

        class Item:
            def __init__(self, author_id, idx):
                self.author_id = author_id
                self.created_at = datetime(2026, 1, 1, idx, tzinfo=dt_timezone.utc)

        items = [Item(1, i) for i in range(5)] + [Item(2, 10), Item(3, 11)]
        result = personalize_feed(
            user=None,
            candidates=items,
            limit=4,
            get_author_id=lambda i: i.author_id,
            get_category_slug=lambda i: None,
            get_market_id=lambda i: None,
            get_points=lambda i: 0,
            get_created_at=lambda i: i.created_at,
            get_engagement=lambda i: 0,
        )
        author_counts = {}
        for item in result:
            author_counts[item.author_id] = author_counts.get(item.author_id, 0) + 1
        self.assertLessEqual(author_counts.get(1, 0), 2)
