"""Tests for user follow and prediction alert notifications."""

from django.core.exceptions import ValidationError
from django.test import Client, TestCase
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


class PredictionNotificationTests(TestCase):
    def setUp(self):
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


class LoginNotificationToastTests(TestCase):
    def setUp(self):
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


class PredictionResolvedNotificationTests(TestCase):
    def setUp(self):
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
