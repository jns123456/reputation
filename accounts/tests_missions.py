"""Daily missions: progress, completion rewards, and streak freezes."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.mission_services import (
    ACTION_VOTE,
    MISSIONS_BY_CODE,
    get_daily_missions,
    record_mission_action,
)
from accounts.models import ActivityStreak, UserMission
from accounts.streak_services import record_activity
from conftest import create_market, create_user
from predictions.services import create_prediction
from reputation.models import PopularityEvent


class MissionTests(TestCase):
    def setUp(self):
        self.user = create_user("missionuser")

    def test_forecast_completes_daily_forecast_mission(self):
        market = create_market(external_id="m-mission", slug="m-mission")
        create_prediction(user=self.user, market=market, predicted_outcome="Yes")

        mission = UserMission.objects.get(user=self.user, code="daily_forecast")
        self.assertIsNotNone(mission.completed_at)
        reward = PopularityEvent.objects.filter(
            user=self.user,
            event_type=PopularityEvent.EventType.MISSION_COMPLETED,
            reason__contains="daily_forecast",
        )
        self.assertEqual(reward.count(), 1)
        self.assertEqual(
            reward.first().points_delta,
            MISSIONS_BY_CODE["daily_forecast"].reward_points,
        )

    def test_reasoned_forecast_also_completes_thesis_mission(self):
        market = create_market(external_id="m-thesis", slug="m-thesis")
        create_prediction(
            user=self.user,
            market=market,
            predicted_outcome="Yes",
            reasoning="x" * 120,
        )
        self.assertTrue(
            UserMission.objects.filter(
                user=self.user, code="daily_thesis", completed_at__isnull=False
            ).exists()
        )

    def test_vote_mission_needs_three_actions(self):
        record_mission_action(self.user, ACTION_VOTE)
        record_mission_action(self.user, ACTION_VOTE)
        mission = UserMission.objects.get(user=self.user, code="daily_engage")
        self.assertIsNone(mission.completed_at)
        self.assertEqual(mission.progress, 2)

        record_mission_action(self.user, ACTION_VOTE)
        mission.refresh_from_db()
        self.assertIsNotNone(mission.completed_at)

    def test_completed_mission_rewards_only_once(self):
        for _ in range(5):
            record_mission_action(self.user, ACTION_VOTE)
        rewards = PopularityEvent.objects.filter(
            user=self.user,
            event_type=PopularityEvent.EventType.MISSION_COMPLETED,
        )
        self.assertEqual(rewards.count(), 1)

    def test_daily_mission_cards_for_anonymous_are_empty(self):
        self.assertEqual(get_daily_missions(None), [])


class StreakFreezeTests(TestCase):
    def setUp(self):
        self.user = create_user("freezeuser")

    def _set_streak(self, **fields):
        # The streak row may already exist (signals pre-create it); update in place.
        ActivityStreak.objects.update_or_create(user=self.user, defaults=fields)

    def test_freeze_token_bridges_a_single_missed_day(self):
        today = timezone.localdate()
        self._set_streak(
            current_streak=5,
            longest_streak=5,
            last_active_date=today - timedelta(days=2),
            freeze_tokens=1,
        )
        streak = record_activity(self.user)
        self.assertEqual(streak.current_streak, 6)
        self.assertEqual(streak.freeze_tokens, 0)

    def test_streak_resets_without_freeze_token(self):
        today = timezone.localdate()
        self._set_streak(
            current_streak=5,
            longest_streak=5,
            last_active_date=today - timedelta(days=2),
            freeze_tokens=0,
        )
        streak = record_activity(self.user)
        self.assertEqual(streak.current_streak, 1)

    def test_freeze_token_earned_at_seven_day_milestone(self):
        today = timezone.localdate()
        self._set_streak(
            current_streak=6,
            longest_streak=6,
            last_active_date=today - timedelta(days=1),
            freeze_tokens=0,
        )
        streak = record_activity(self.user)
        self.assertEqual(streak.current_streak, 7)
        self.assertEqual(streak.freeze_tokens, 1)
