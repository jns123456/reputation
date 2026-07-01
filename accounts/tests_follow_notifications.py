"""Tests for user follow and prediction alert notifications."""

from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.follow_services import toggle_follow
from accounts.models import Notification, NotificationPreference, UserFollow
from accounts.notification_services import (
    LOGIN_NOTIFICATION_TOAST_SESSION_KEY,
    consume_login_notification_toast,
    get_or_create_notification_preferences,
    get_unread_notification_count,
    notify_followers_of_prediction,
    queue_login_notification_toast,
)
from comments.models import Comment, Vote
from comments.services import cast_vote
from conftest import create_market, create_user
from markets.models import Market
from predictions.services import create_prediction, resolve_market_predictions
from reputation.services import calculate_reputation_delta


class SkipMarketRefreshTestsMixin:
    def setUp(self):
        self._refresh_odds_patcher = patch(
            "predictions.services._refresh_market_odds",
            side_effect=lambda market: market,
        )
        self._refresh_odds_patcher.start()
        self.addCleanup(self._refresh_odds_patcher.stop)
        super().setUp()


class FollowServiceTests(TestCase):
    def setUp(self):
        self.follower = create_user("follower")
        self.target = create_user("target")

    def test_toggle_follow_creates_and_removes_relation(self):
        self.assertTrue(toggle_follow(follower=self.follower, following_user=self.target))
        self.assertTrue(
            UserFollow.objects.filter(follower=self.follower, following=self.target).exists()
        )
        self.assertFalse(toggle_follow(follower=self.follower, following_user=self.target))
        self.assertFalse(
            UserFollow.objects.filter(follower=self.follower, following=self.target).exists()
        )

    def test_cannot_follow_self(self):
        with self.assertRaises(ValidationError):
            toggle_follow(follower=self.follower, following_user=self.follower)


@override_settings(EMAIL_VERIFICATION_REQUIRED=False)
class FollowToggleViewTests(TestCase):
    def setUp(self):
        self.follower = create_user("followview1")
        self.target = create_user("followview2")
        self.client = Client()
        self.client.force_login(self.follower)
        self.url = reverse("accounts:follow_toggle")

    def test_follow_toggle_via_htmx_updates_button(self):
        response = self.client.post(
            self.url,
            {"username": self.target.username},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Following")
        self.assertTrue(
            UserFollow.objects.filter(follower=self.follower, following=self.target).exists()
        )

    def test_follow_toggle_via_htmx_can_unfollow(self):
        toggle_follow(follower=self.follower, following_user=self.target)
        response = self.client.post(
            self.url,
            {"username": self.target.username},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Follow")
        self.assertFalse(
            UserFollow.objects.filter(follower=self.follower, following=self.target).exists()
        )

    def test_follow_toggle_via_htmx_list_context_shows_unfollow(self):
        response = self.client.post(
            self.url,
            {"username": self.target.username, "context": "list"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Unfollow")

    def test_follow_toggle_via_htmx_list_context_can_unfollow(self):
        toggle_follow(follower=self.follower, following_user=self.target)
        response = self.client.post(
            self.url,
            {"username": self.target.username, "context": "list"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Follow")

    def test_follow_toggle_without_htmx_redirects_to_profile(self):
        response = self.client.post(self.url, {"username": self.target.username})
        self.assertRedirects(
            response,
            reverse("accounts:profile", kwargs={"username": self.target.username}),
        )
        self.assertTrue(
            UserFollow.objects.filter(follower=self.follower, following=self.target).exists()
        )

    def test_follow_toggle_survives_notification_failure(self):
        with patch(
            "accounts.notification_services.notify_new_follower",
            side_effect=RuntimeError("notify failed"),
        ):
            response = self.client.post(
                self.url,
                {"username": self.target.username},
                HTTP_HX_REQUEST="true",
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Following")
        self.assertTrue(
            UserFollow.objects.filter(follower=self.follower, following=self.target).exists()
        )


@override_settings(EMAIL_VERIFICATION_REQUIRED=True)
class FollowToggleEmailGateTests(TestCase):
    def setUp(self):
        self.follower = create_user("followgate1", email_verified_at=None)
        self.target = create_user("followgate2")
        self.client = Client()
        self.client.force_login(self.follower)
        self.url = reverse("accounts:follow_toggle")

    def test_unverified_user_htmx_follow_gets_hx_redirect(self):
        response = self.client.post(
            self.url,
            {"username": self.target.username},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 204)
        self.assertIn("HX-Redirect", response.headers)
        self.assertFalse(
            UserFollow.objects.filter(follower=self.follower, following=self.target).exists()
        )


class PredictionNotificationTests(SkipMarketRefreshTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.follower = create_user("alertuser")
        self.predictor = create_user("predictor")
        self.market = create_market(slug="alert-market", external_id="alert-m1")
        toggle_follow(follower=self.follower, following_user=self.predictor)

    def test_create_prediction_notifies_followers(self):
        prediction = create_prediction(
            user=self.predictor,
            market=self.market,
            predicted_outcome="Yes",
        )
        notifications = Notification.objects.filter(recipient=self.follower)
        self.assertEqual(notifications.count(), 1)
        notification = notifications.first()
        self.assertEqual(notification.actor, self.predictor)
        self.assertEqual(notification.prediction, prediction)
        self.assertEqual(
            notification.notification_type,
            Notification.NotificationType.FOLLOWED_USER_PREDICTION,
        )
        self.assertIsNone(notification.read_at)

    def test_respects_notification_preferences(self):
        preferences = get_or_create_notification_preferences(self.follower)
        preferences.notify_followed_predictions = False
        preferences.save()

        create_prediction(
            user=self.predictor,
            market=self.market,
            predicted_outcome="Yes",
        )
        self.assertEqual(Notification.objects.filter(recipient=self.follower).count(), 0)

    def test_notify_followers_direct_respects_in_app_preference(self):
        preferences = get_or_create_notification_preferences(self.follower)
        preferences.notify_in_app = False
        preferences.save()

        prediction = create_prediction(
            user=self.predictor,
            market=self.market,
            predicted_outcome="No",
        )
        created = notify_followers_of_prediction(prediction=prediction)
        self.assertEqual(created, [])
        self.assertEqual(Notification.objects.filter(recipient=self.follower).count(), 0)

    def test_unread_count(self):
        create_prediction(
            user=self.predictor,
            market=self.market,
            predicted_outcome="Yes",
        )
        self.assertEqual(get_unread_notification_count(user=self.follower), 1)


class FollowerNotificationTests(TestCase):
    def setUp(self):
        self.follower = create_user("newfollower")
        self.target = create_user("followed")

    def test_follow_creates_notification_for_target(self):
        toggle_follow(follower=self.follower, following_user=self.target)
        notification = Notification.objects.get(recipient=self.target)
        self.assertEqual(notification.actor, self.follower)
        self.assertEqual(notification.notification_type, Notification.NotificationType.NEW_FOLLOWER)

    def test_unfollow_does_not_create_notification(self):
        toggle_follow(follower=self.follower, following_user=self.target)
        toggle_follow(follower=self.follower, following_user=self.target)
        self.assertEqual(Notification.objects.filter(recipient=self.target).count(), 1)


class NotificationOpenTests(TestCase):
    def setUp(self):
        self.recipient = create_user("notifyme")
        self.actor = create_user("actor")
        self.market = create_market(slug="notify-market", external_id="notify-m1")
        self.prediction = create_prediction(
            user=self.actor,
            market=self.market,
            predicted_outcome="Yes",
        )
        self.notification = Notification.objects.create(
            recipient=self.recipient,
            actor=self.actor,
            notification_type=Notification.NotificationType.FOLLOWED_USER_PREDICTION,
            prediction=self.prediction,
        )
        self.client = Client()
        self.client.force_login(self.recipient)

    def test_open_marks_notification_read_and_redirects(self):
        url = reverse(
            "accounts:notification_open",
            kwargs={"notification_id": self.notification.id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response["Location"],
            reverse("markets:detail", kwargs={"slug": self.market.slug}),
        )
        self.notification.refresh_from_db()
        self.assertIsNotNone(self.notification.read_at)
        self.assertEqual(get_unread_notification_count(user=self.recipient), 0)

    def test_dropdown_does_not_show_mark_all_read(self):
        response = self.client.get(reverse("accounts:notifications_dropdown"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Mark all read")
        self.assertNotContains(response, "Marcar todas como leídas")

    def test_notifications_page_does_not_show_mark_all_read(self):
        response = self.client.get(reverse("accounts:notifications"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Mark all as read")
        self.assertNotContains(response, "Marcar todo como leído")


class LoginNotificationToastTests(TestCase):
    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.follower = create_user("toastfollower")
        self.target = create_user("toasttarget")
        self.client = Client()

    def test_login_shows_toast_when_unread_notifications_exist(self):
        toggle_follow(follower=self.follower, following_user=self.target)
        response = self.client.post(
            reverse("accounts:login"),
            {"username": self.target.username, "password": "testpass123"},
            follow=True,
        )
        self.assertContains(response, "You have 1 new alert")
        self.assertNotIn(LOGIN_NOTIFICATION_TOAST_SESSION_KEY, self.client.session)

    def test_toast_is_shown_once_after_login(self):
        toggle_follow(follower=self.follower, following_user=self.target)
        self.client.login(username=self.target.username, password="testpass123")
        session = self.client.session
        session[LOGIN_NOTIFICATION_TOAST_SESSION_KEY] = True
        session.save()

        profile_response = self.client.get(
            reverse("accounts:profile", kwargs={"username": self.target.username})
        )
        self.assertContains(profile_response, "You have 1 new alert")
        self.assertNotIn(LOGIN_NOTIFICATION_TOAST_SESSION_KEY, self.client.session)

        profile_response_again = self.client.get(
            reverse("accounts:profile", kwargs={"username": self.target.username})
        )
        self.assertNotContains(profile_response_again, "You have 1 new alert")

    def test_queue_login_notification_toast_skips_when_no_unread(self):
        self.client.force_login(self.target)
        request = self.client.request().wsgi_request
        request.user = self.target
        queue_login_notification_toast(request=request)
        self.assertNotIn(LOGIN_NOTIFICATION_TOAST_SESSION_KEY, request.session)
        self.assertIsNone(consume_login_notification_toast(request=request))


class VoteNotificationTests(TestCase):
    def setUp(self):
        self.author = create_user("author")
        self.voter = create_user("voter")
        self.market = create_market(slug="vote-market", external_id="vote-m1")
        self.comment = Comment.objects.create(
            user=self.author,
            market=self.market,
            body="Test comment",
        )

    def test_upvote_creates_notification(self):
        cast_vote(
            user=self.voter,
            target_type=Vote.TargetType.COMMENT,
            target_id=self.comment.id,
            value=1,
        )
        notification = Notification.objects.get(recipient=self.author)
        self.assertEqual(notification.notification_type, Notification.NotificationType.UPVOTE_RECEIVED)
        self.assertEqual(notification.actor, self.voter)

    def test_downvote_creates_notification(self):
        cast_vote(
            user=self.voter,
            target_type=Vote.TargetType.COMMENT,
            target_id=self.comment.id,
            value=-1,
        )
        notification = Notification.objects.get(recipient=self.author)
        self.assertEqual(notification.notification_type, Notification.NotificationType.DOWNVOTE_RECEIVED)

    def test_prediction_vote_switch_updates_notification(self):
        prediction = create_prediction(
            user=self.author,
            market=self.market,
            predicted_outcome="Yes",
        )
        cast_vote(
            user=self.voter,
            target_type=Vote.TargetType.PREDICTION,
            target_id=prediction.id,
            value=1,
        )
        cast_vote(
            user=self.voter,
            target_type=Vote.TargetType.PREDICTION,
            target_id=prediction.id,
            value=-1,
        )
        cast_vote(
            user=self.voter,
            target_type=Vote.TargetType.PREDICTION,
            target_id=prediction.id,
            value=1,
        )
        notifications = Notification.objects.filter(
            recipient=self.author,
            prediction=prediction,
        )
        self.assertEqual(notifications.count(), 1)
        self.assertEqual(
            notifications.get().notification_type,
            Notification.NotificationType.UPVOTE_RECEIVED,
        )

    def test_respects_vote_notification_preference(self):
        preferences = get_or_create_notification_preferences(self.author)
        preferences.notify_votes_received = False
        preferences.save()
        cast_vote(
            user=self.voter,
            target_type=Vote.TargetType.COMMENT,
            target_id=self.comment.id,
            value=1,
        )
        self.assertEqual(Notification.objects.filter(recipient=self.author).count(), 0)


class PredictionResolvedNotificationTests(SkipMarketRefreshTestsMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.user = create_user("resolver")
        self.market = create_market(slug="resolve-market", external_id="resolve-m1")
        self.prediction = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
        )

    def _resolve_market(self, *, outcome):
        self.market.status = Market.Status.RESOLVED
        self.market.resolved_outcome = outcome
        self.market.save()
        resolve_market_predictions(self.market)

    def test_resolve_creates_notification_with_reputation_points(self):
        self._resolve_market(outcome="Yes")
        notification = Notification.objects.get(recipient=self.user)
        self.assertEqual(
            notification.notification_type,
            Notification.NotificationType.PREDICTION_RESOLVED,
        )
        self.assertEqual(notification.prediction, self.prediction)
        self.assertIsNotNone(notification.reputation_event)
        expected_delta = calculate_reputation_delta(
            is_correct=True,
            predicted_outcome=self.prediction.predicted_outcome,
            probability_snapshot=self.prediction.probability_at_prediction_time,
        )
        self.assertEqual(notification.reputation_event.points_delta, expected_delta)

    def test_incorrect_forecast_shows_negative_points(self):
        self._resolve_market(outcome="No")
        notification = Notification.objects.get(recipient=self.user)
        expected_delta = calculate_reputation_delta(
            is_correct=False,
            predicted_outcome=self.prediction.predicted_outcome,
            probability_snapshot=self.prediction.probability_at_prediction_time,
        )
        self.assertEqual(notification.reputation_event.points_delta, expected_delta)
        self.assertLess(expected_delta, 0)

    def test_respects_prediction_resolved_preference(self):
        preferences = get_or_create_notification_preferences(self.user)
        preferences.notify_prediction_resolved = False
        preferences.save()
        self._resolve_market(outcome="Yes")
        self.assertEqual(Notification.objects.filter(recipient=self.user).count(), 0)

    def test_default_preference_is_enabled(self):
        preferences = get_or_create_notification_preferences(self.user)
        self.assertTrue(preferences.notify_prediction_resolved)


class NotificationViewsPerformanceTests(SkipMarketRefreshTestsMixin, TestCase):
    """Dropdown and list views must not recompute challenge standings per row."""

    def setUp(self):
        super().setUp()
        from django.core.cache import cache

        cache.clear()
        from django.utils import timezone

        from accounts.models import UserFollow
        from challenges.notification_services import notify_challenge_market_resolved
        from challenges.services import accept_challenge, create_challenge

        self.recipient = create_user("notifperf")
        self.creator = create_user("chcreator")
        UserFollow.objects.create(follower=self.recipient, following=self.creator)
        UserFollow.objects.create(follower=self.creator, following=self.recipient)

        self.market = create_market(slug="ch-perf-m1", external_id="ch-perf-m1")
        self.challenge = create_challenge(
            creator=self.creator,
            title="Perf challenge",
            market_ids=[self.market.id],
            opponent_ids=[self.recipient.id],
        )
        accept_challenge(challenge=self.challenge, user=self.recipient)
        self.challenge.refresh_from_db()
        if not self.challenge.started_at:
            self.challenge.started_at = timezone.now()
            self.challenge.status = self.challenge.Status.ACTIVE
            self.challenge.save(update_fields=["started_at", "status"])

        self.market.status = Market.Status.RESOLVED
        self.market.resolved_outcome = "Yes"
        self.market.resolution_date = timezone.now()
        self.market.save()
        notify_challenge_market_resolved(challenge=self.challenge, market=self.market)

        for index in range(7):
            Notification.objects.create(
                recipient=self.recipient,
                actor=self.creator,
                notification_type=Notification.NotificationType.NEW_FOLLOWER,
            )

        self.client.force_login(self.recipient)

    def test_notifications_dropdown_query_count_bounded(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        url = reverse("accounts:notifications_dropdown")
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Perf challenge")
        self.assertLessEqual(len(ctx.captured_queries), 10)

    def test_notifications_list_query_count_bounded(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        url = reverse("accounts:notifications")
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Perf challenge")
        self.assertLessEqual(len(ctx.captured_queries), 10)

    def test_dropdown_query_count_stable_with_more_challenge_rows(self):
        from django.core.cache import cache
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from challenges.notification_services import notify_challenge_market_resolved

        url = reverse("accounts:notifications_dropdown")
        cache.clear()
        with CaptureQueriesContext(connection) as baseline:
            self.client.get(url)
        baseline_count = len(baseline.captured_queries)

        market_two = create_market(slug="ch-perf-m2", external_id="ch-perf-m2")
        self.challenge.challenge_markets.create(market=market_two, position=2)
        market_two.status = Market.Status.RESOLVED
        market_two.resolved_outcome = "No"
        market_two.save()
        notify_challenge_market_resolved(challenge=self.challenge, market=market_two)

        cache.clear()
        with CaptureQueriesContext(connection) as after:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(after.captured_queries), baseline_count)

    def test_dropdown_uses_cached_recent_notifications_on_repeat(self):
        from django.core.cache import cache
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        url = reverse("accounts:notifications_dropdown")
        cache.clear()
        with CaptureQueriesContext(connection) as first:
            self.client.get(url)
        first_count = len(first.captured_queries)

        with CaptureQueriesContext(connection) as second:
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Perf challenge")
        self.assertLess(len(second.captured_queries), first_count)
        self.assertLessEqual(len(second.captured_queries), 2)
