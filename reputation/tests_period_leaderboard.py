"""Period (30-day) leaderboards, Agent Arena filtering, and season awards."""

from django.test import TestCase
from django.urls import reverse

from conftest import create_market, create_user
from predictions.models import Prediction
from reputation.models import ReputationEvent, SeasonAward
from reputation.period_leaderboard import get_top_predictors_for_period
from reputation.season_services import finalize_season, season_date_range


def _scored_prediction(user, market, *, points, correct=True, n=0):
    prediction = Prediction.objects.create(
        user=user,
        market=market,
        predicted_outcome="Yes",
        status=Prediction.Status.RESOLVED,
        is_correct=correct,
    )
    ReputationEvent.objects.create(
        user=user,
        prediction=prediction,
        event_type=(
            ReputationEvent.EventType.CORRECT_PREDICTION
            if correct
            else ReputationEvent.EventType.INCORRECT_PREDICTION
        ),
        points_delta=points,
        reason=f"test event {n}",
    )
    return prediction


class PeriodLeaderboardTests(TestCase):
    def setUp(self):
        self.market = create_market(external_id="plb", slug="plb")
        self.human = create_user("humanlb")
        self.agent = create_user("agentlb", account_type="declared_agent")

    def test_recent_events_rank_users(self):
        _scored_prediction(self.human, self.market, points=40)
        market2 = create_market(external_id="plb2", slug="plb2")
        _scored_prediction(self.agent, market2, points=10)

        rows = get_top_predictors_for_period(days=30, limit=10, mode="absolute")
        self.assertEqual([row.user.id for row in rows], [self.human.id, self.agent.id])
        self.assertEqual(rows[0].reputation_points, 40)
        self.assertEqual(rows[0].scored_forecast_count, 1)

    def test_agents_only_filter(self):
        _scored_prediction(self.human, self.market, points=40)
        market2 = create_market(external_id="plb3", slug="plb3")
        _scored_prediction(self.agent, market2, points=10)

        rows = get_top_predictors_for_period(
            days=30, limit=10, mode="absolute", agents_only=True
        )
        self.assertEqual([row.user.id for row in rows], [self.agent.id])

    def test_leaderboard_page_supports_period_param(self):
        response = self.client.get(
            reverse("dashboard:reputation_leaderboard"), {"period": "30d"}
        )
        self.assertEqual(response.status_code, 200)

    def test_agent_arena_page_renders(self):
        response = self.client.get(reverse("dashboard:agent_arena"))
        self.assertEqual(response.status_code, 200)

    def test_agent_arena_page_renders_in_spanish(self):
        response = self.client.get(
            reverse("dashboard:agent_arena"), HTTP_ACCEPT_LANGUAGE="es"
        )
        self.assertEqual(response.status_code, 200)


class SeasonAwardTests(TestCase):
    def test_finalize_season_is_idempotent(self):
        user = create_user("seasonuser")
        market = create_market(external_id="season-m", slug="season-m")

        # Use last fully-completed season relative to the events we create now.
        from reputation.season_services import previous_season_code

        season = previous_season_code()
        since, until = season_date_range(season)

        for index in range(6):
            m = create_market(external_id=f"season-{index}", slug=f"season-{index}")
            prediction = _scored_prediction(user, m, points=10, n=index)
            ReputationEvent.objects.filter(prediction=prediction).update(
                created_at=since
            )

        created = finalize_season(season)
        self.assertEqual(created, 1)
        award = SeasonAward.objects.get(user=user, season=season)
        self.assertEqual(award.rank, 1)
        self.assertEqual(award.reputation_points, 60)

        # Second run creates nothing new.
        self.assertEqual(finalize_season(season), 0)

    def test_users_below_min_sample_get_no_award(self):
        user = create_user("seasonsmall")
        from reputation.season_services import previous_season_code

        season = previous_season_code()
        since, _until = season_date_range(season)
        market = create_market(external_id="season-x", slug="season-x")
        prediction = _scored_prediction(user, market, points=50)
        ReputationEvent.objects.filter(prediction=prediction).update(created_at=since)

        self.assertEqual(finalize_season(season), 0)
        self.assertFalse(SeasonAward.objects.filter(user=user).exists())
