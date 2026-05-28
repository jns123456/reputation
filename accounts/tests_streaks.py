"""Tests for activity streaks — the daily-habit engagement loop."""

from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase

from accounts.models import ActivityStreak
from accounts.streak_services import (
    STREAK_MILESTONES,
    get_streak,
    get_streaks_at_risk,
    record_activity,
)
from conftest import create_market, create_user


class RecordActivityTests(TestCase):
    def setUp(self):
        self.user = create_user("streaker")
        self.day = date(2026, 5, 1)

    def test_first_activity_starts_streak_at_one(self):
        streak = record_activity(self.user, when=self.day)
        self.assertEqual(streak.current_streak, 1)
        self.assertEqual(streak.longest_streak, 1)
        self.assertEqual(streak.last_active_date, self.day)

    def test_same_day_activity_is_idempotent(self):
        record_activity(self.user, when=self.day)
        streak = record_activity(self.user, when=self.day)
        self.assertEqual(streak.current_streak, 1)

    def test_consecutive_days_increment_streak(self):
        record_activity(self.user, when=self.day)
        record_activity(self.user, when=self.day + timedelta(days=1))
        streak = record_activity(self.user, when=self.day + timedelta(days=2))
        self.assertEqual(streak.current_streak, 3)
        self.assertEqual(streak.longest_streak, 3)

    def test_gap_resets_streak_but_keeps_longest(self):
        for i in range(3):
            record_activity(self.user, when=self.day + timedelta(days=i))
        # Skip a day -> streak resets.
        streak = record_activity(self.user, when=self.day + timedelta(days=5))
        self.assertEqual(streak.current_streak, 1)
        self.assertEqual(streak.longest_streak, 3)

    def test_milestone_awards_popularity_points(self):
        for i in range(7):
            record_activity(self.user, when=self.day + timedelta(days=i))
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.popularity_points, STREAK_MILESTONES[7])

    def test_record_activity_ignores_anonymous(self):
        class Anon:
            is_authenticated = False
            id = None

        self.assertIsNone(record_activity(Anon(), when=self.day))


class StreakDisplayTests(TestCase):
    def setUp(self):
        self.user = create_user("displayer")

    def _streak(self, *, current, longest, last_active_date):
        streak = ActivityStreak.objects.get(user=self.user)
        streak.current_streak = current
        streak.longest_streak = longest
        streak.last_active_date = last_active_date
        streak.save()
        return streak

    def test_active_today_counts(self):
        today = date(2026, 5, 10)
        streak = self._streak(current=4, longest=4, last_active_date=today)
        self.assertEqual(streak.display_streak(today=today), 4)
        self.assertFalse(streak.is_at_risk(today=today))

    def test_active_yesterday_is_alive_but_at_risk(self):
        today = date(2026, 5, 10)
        streak = self._streak(
            current=4, longest=4, last_active_date=today - timedelta(days=1)
        )
        self.assertEqual(streak.display_streak(today=today), 4)
        self.assertTrue(streak.is_at_risk(today=today))

    def test_lapsed_streak_displays_zero(self):
        today = date(2026, 5, 10)
        streak = self._streak(
            current=4, longest=4, last_active_date=today - timedelta(days=3)
        )
        self.assertEqual(streak.display_streak(today=today), 0)
        self.assertFalse(streak.is_at_risk(today=today))


class StreaksAtRiskTests(TestCase):
    def test_only_yesterday_streaks_above_threshold_are_returned(self):
        today = date(2026, 5, 10)
        yesterday = today - timedelta(days=1)

        at_risk_user = create_user("atrisk")
        ActivityStreak.objects.filter(user=at_risk_user).update(
            current_streak=5, last_active_date=yesterday
        )

        active_user = create_user("activetoday")
        ActivityStreak.objects.filter(user=active_user).update(
            current_streak=5, last_active_date=today
        )

        tiny_user = create_user("tiny")
        ActivityStreak.objects.filter(user=tiny_user).update(
            current_streak=1, last_active_date=yesterday
        )

        at_risk_ids = set(
            get_streaks_at_risk(today=today).values_list("user_id", flat=True)
        )
        self.assertIn(at_risk_user.id, at_risk_ids)
        self.assertNotIn(active_user.id, at_risk_ids)
        self.assertNotIn(tiny_user.id, at_risk_ids)


class StreakActionHookTests(TestCase):
    def setUp(self):
        self._refresh_odds_patcher = patch(
            "predictions.services._refresh_market_odds",
            side_effect=lambda market: market,
        )
        self._refresh_odds_patcher.start()
        self.addCleanup(self._refresh_odds_patcher.stop)
        self.user = create_user("predictor")
        self.market = create_market()

    def test_creating_prediction_records_activity(self):
        from predictions.services import create_prediction

        self.assertFalse(ActivityStreak.objects.filter(user=self.user, last_active_date__isnull=False).exists())
        create_prediction(user=self.user, market=self.market, predicted_outcome="Yes")
        streak = get_streak(self.user)
        self.assertEqual(streak.current_streak, 1)
        self.assertIsNotNone(streak.last_active_date)
