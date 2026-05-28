"""Tests for outbound engagement email (transactional, digest, streak risk)."""

from datetime import date, timedelta

from django.core import mail
from django.test import TestCase, override_settings

from accounts.email_services import (
    send_daily_digest,
    send_notification_email,
    send_streak_risk_reminder,
)
from accounts.models import ActivityStreak, Notification, NotificationPreference
from conftest import create_user


def _set_prefs(user, **kwargs):
    NotificationPreference.objects.filter(user=user).update(**kwargs)


@override_settings(ENGAGEMENT_EMAILS_ENABLED=True)
class NotificationEmailTests(TestCase):
    def setUp(self):
        self.actor = create_user("actor")
        self.recipient = create_user("recipient")

    def _make_follow_notification(self):
        return Notification.objects.create(
            recipient=self.recipient,
            actor=self.actor,
            notification_type=Notification.NotificationType.NEW_FOLLOWER,
        )

    def test_email_sent_when_opted_in(self):
        _set_prefs(self.recipient, notify_email=True, notify_new_follower=True)
        notification = self._make_follow_notification()
        mail.outbox = []

        result = send_notification_email(notification.id)

        self.assertTrue(result)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.recipient.email])

    def test_no_email_when_global_email_off(self):
        _set_prefs(self.recipient, notify_email=False, notify_new_follower=True)
        notification = self._make_follow_notification()
        mail.outbox = []

        self.assertFalse(send_notification_email(notification.id))
        self.assertEqual(len(mail.outbox), 0)

    def test_no_email_when_type_preference_off(self):
        _set_prefs(self.recipient, notify_email=True, notify_new_follower=False)
        notification = self._make_follow_notification()
        mail.outbox = []

        self.assertFalse(send_notification_email(notification.id))
        self.assertEqual(len(mail.outbox), 0)

    def test_no_email_without_address(self):
        self.recipient.email = ""
        self.recipient.save(update_fields=["email"])
        _set_prefs(self.recipient, notify_email=True, notify_new_follower=True)
        notification = self._make_follow_notification()
        mail.outbox = []

        self.assertFalse(send_notification_email(notification.id))
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(ENGAGEMENT_EMAILS_ENABLED=False)
    def test_master_switch_disables_email(self):
        _set_prefs(self.recipient, notify_email=True, notify_new_follower=True)
        notification = self._make_follow_notification()
        mail.outbox = []

        self.assertFalse(send_notification_email(notification.id))
        self.assertEqual(len(mail.outbox), 0)


@override_settings(ENGAGEMENT_EMAILS_ENABLED=True)
class StreakRiskEmailTests(TestCase):
    def setUp(self):
        self.user = create_user("riskuser")

    def test_reminder_sent_when_opted_in(self):
        _set_prefs(self.user, notify_email=True)
        streak = ActivityStreak.objects.get(user=self.user)
        streak.current_streak = 6
        streak.save(update_fields=["current_streak"])
        mail.outbox = []

        self.assertTrue(send_streak_risk_reminder(streak))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("6", mail.outbox[0].subject)

    def test_reminder_blocked_without_email_pref(self):
        _set_prefs(self.user, notify_email=False)
        streak = ActivityStreak.objects.get(user=self.user)
        mail.outbox = []

        self.assertFalse(send_streak_risk_reminder(streak))
        self.assertEqual(len(mail.outbox), 0)


@override_settings(ENGAGEMENT_EMAILS_ENABLED=True)
class DailyDigestTests(TestCase):
    def setUp(self):
        self.actor = create_user("digest_actor")
        self.user = create_user("digest_user")

    def test_digest_sent_when_recent_activity(self):
        _set_prefs(self.user, notify_email=True)
        Notification.objects.create(
            recipient=self.user,
            actor=self.actor,
            notification_type=Notification.NotificationType.NEW_FOLLOWER,
        )
        mail.outbox = []

        self.assertTrue(send_daily_digest(self.user.id))
        self.assertEqual(len(mail.outbox), 1)

    def test_no_digest_when_nothing_to_report(self):
        _set_prefs(self.user, notify_email=True)
        mail.outbox = []

        self.assertFalse(send_daily_digest(self.user.id))
        self.assertEqual(len(mail.outbox), 0)
