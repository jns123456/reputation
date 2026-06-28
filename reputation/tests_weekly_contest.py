"""Weekly reputation contest — standings, winners, login announcement."""

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from datetime import date, timedelta

from conftest import create_market, create_user
from predictions.models import Prediction
from reputation.models import ReputationEvent, WeeklyContestWinner
from reputation.period_leaderboard import get_top_predictors_between
from reputation.weekly_contest_services import (
    build_contest_week_nav,
    current_week_code,
    finalize_weekly_contest,
    get_past_weekly_contest_winners,
    get_weekly_contest_winners_for_week,
    is_completed_contest_week,
    is_live_contest_week,
    is_upcoming_contest_week,
    list_contest_week_codes,
    sunday_start_for_date,
    week_date_range,
    week_code_for_date,
)


def _scored_prediction(user, market, *, points, correct=True):
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
        reason="weekly contest test",
    )
    return prediction


class WeeklyContestServicesTests(TestCase):
    def setUp(self):
        self.market = create_market(external_id="wc1", slug="wc1")
        self.leader = create_user("wcleader")
        self.runner_up = create_user("wcrunner")

    def test_week_starts_on_sunday(self):
        fri = date(2026, 6, 19)
        sun = date(2026, 6, 21)
        self.assertEqual(sunday_start_for_date(fri), date(2026, 6, 14))
        self.assertEqual(sunday_start_for_date(sun), date(2026, 6, 21))
        self.assertEqual(week_code_for_date(sun), "2026-06-21")
        since, until = week_date_range("2026-06-21")
        self.assertEqual(timezone.localtime(since).date(), date(2026, 6, 21))
        self.assertEqual((timezone.localtime(until) - timedelta(seconds=1)).date(), date(2026, 6, 27))

    @override_settings(WEEKLY_CONTEST_FIRST_WEEK_START="2026-06-21")
    def test_before_launch_shows_first_week_as_upcoming(self):
        self.assertEqual(current_week_code(today=date(2026, 6, 19)), "2026-06-21")
        self.assertTrue(is_upcoming_contest_week(today=date(2026, 6, 19)))
        self.assertFalse(is_live_contest_week(today=date(2026, 6, 19)))
        self.assertTrue(is_live_contest_week(today=date(2026, 6, 21)))

    @override_settings(WEEKLY_CONTEST_FIRST_WEEK_START="2020-01-01")
    def test_week_bounds_aggregate_current_week_events(self):
        since, until = week_date_range(current_week_code())
        _scored_prediction(self.leader, self.market, points=50)
        market2 = create_market(external_id="wc2", slug="wc2")
        _scored_prediction(self.runner_up, market2, points=20)

        rows = get_top_predictors_between(since=since, until=until, limit=10, mode="absolute")
        self.assertEqual(rows[0].user.id, self.leader.id)
        self.assertEqual(rows[0].reputation_points, 50)

    @override_settings(WEEKLY_CONTEST_FIRST_WEEK_START="2020-01-01")
    def test_relative_weekly_contest_ranks_by_rep_per_forecast_at_min_scored(self):
        """Users with exactly min scored forecasts qualify for weekly relative ranking."""
        week_code = "2020-03-08"
        since, _until = week_date_range(week_code)
        exact_min = create_user("wc_exact_min")
        above_min = create_user("wc_above_min")

        for index in range(10):
            market = create_market(external_id=f"wc-min-{index}", slug=f"wc-min-{index}")
            prediction = _scored_prediction(exact_min, market, points=2)
            ReputationEvent.objects.filter(prediction=prediction).update(created_at=since)

        for index in range(18):
            market = create_market(external_id=f"wc-above-{index}", slug=f"wc-above-{index}")
            prediction = _scored_prediction(above_min, market, points=1 if index % 3 else -1)
            ReputationEvent.objects.filter(prediction=prediction).update(created_at=since)

        from reputation.weekly_contest_services import qualifies_for_weekly_contest

        rows = get_top_predictors_between(
            since=since,
            until=week_date_range(week_code)[1],
            limit=10,
            mode="relative",
            relative_qualifies_fn=qualifies_for_weekly_contest,
        )
        qualified = [row for row in rows if qualifies_for_weekly_contest(row.scored_forecast_count)]
        self.assertEqual(qualified[0].user.id, exact_min.id)
        self.assertGreater(qualified[0].reputation_score, qualified[1].reputation_score)

    @override_settings(WEEKLY_CONTEST_FIRST_WEEK_START="2020-01-01")
    def test_finalize_skips_users_below_min_scored_forecasts(self):
        week_code = "2020-03-08"
        since, _until = week_date_range(week_code)
        for index in range(9):
            market = create_market(external_id=f"wc-low-{index}", slug=f"wc-low-{index}")
            prediction = _scored_prediction(self.leader, market, points=20)
            ReputationEvent.objects.filter(prediction=prediction).update(created_at=since)

        self.assertEqual(finalize_weekly_contest(week_code), 0)

    @override_settings(WEEKLY_CONTEST_FIRST_WEEK_START="2020-01-01")
    def test_finalize_weekly_contest_is_idempotent(self):
        week_code = "2020-03-08"
        since, _until = week_date_range(week_code)
        for index in range(12):
            market = create_market(external_id=f"wc-old-{index}", slug=f"wc-old-{index}")
            prediction = _scored_prediction(self.leader, market, points=5)
            ReputationEvent.objects.filter(prediction=prediction).update(created_at=since)

        created = finalize_weekly_contest(week_code)
        self.assertEqual(created, 2)
        self.assertEqual(WeeklyContestWinner.objects.filter(week_code=week_code).count(), 2)
        self.assertEqual(finalize_weekly_contest(week_code), 0)

    @override_settings(WEEKLY_CONTEST_FIRST_WEEK_START="2020-01-01")
    def test_get_past_weekly_contest_winners_groups_by_week(self):
        week_code = "2020-03-08"
        since, _until = week_date_range(week_code)
        for index in range(12):
            market = create_market(external_id=f"wc-hist-{index}", slug=f"wc-hist-{index}")
            prediction = _scored_prediction(self.leader, market, points=5)
            ReputationEvent.objects.filter(prediction=prediction).update(created_at=since)

        finalize_weekly_contest(week_code)
        history = get_past_weekly_contest_winners()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["week_code"], week_code)
        self.assertIn("absolute", history[0]["winners"])
        self.assertIn("relative", history[0]["winners"])
        winners = get_weekly_contest_winners_for_week(week_code)
        self.assertEqual(winners["absolute"].user_id, self.leader.id)

    @override_settings(WEEKLY_CONTEST_FIRST_WEEK_START="2026-06-21")
    def test_list_contest_week_codes_from_launch(self):
        weeks = list_contest_week_codes(today=date(2026, 6, 28))
        self.assertEqual(weeks, ["2026-06-28", "2026-06-21"])

    def test_is_completed_contest_week_after_window_ends(self):
        week_code = "2020-03-08"
        self.assertTrue(is_completed_contest_week(week_code=week_code))


@override_settings(WEEKLY_CONTEST_ENABLED=True)
class WeeklyContestViewTests(TestCase):
    @override_settings(WEEKLY_CONTEST_ENABLED=True, WEEKLY_CONTEST_FIRST_WEEK_START="2026-06-21")
    def test_weekly_contest_page_shows_launch_week_before_start(self):
        response = self.client.get(reverse("dashboard:weekly_contest"))
        self.assertContains(response, "Jun 21")
        self.assertContains(response, "Jun 27")
        self.assertNotContains(response, "Jun 14")

    def test_weekly_contest_page_renders(self):
        response = self.client.get(reverse("dashboard:weekly_contest"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Weekly Contest")

    def test_weekly_contest_page_renders_in_spanish(self):
        response = self.client.get(
            reverse("dashboard:weekly_contest"),
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Concurso")
        self.assertContains(response, "Semanal")

    @override_settings(WEEKLY_CONTEST_FIRST_WEEK_START="2020-01-01")
    def test_weekly_contest_page_shows_past_winners(self):
        week_code = "2020-03-08"
        since, _until = week_date_range(week_code)
        leader = create_user("wchist")
        for index in range(12):
            m = create_market(external_id=f"wc-hist-view-{index}", slug=f"wc-hist-view-{index}")
            prediction = _scored_prediction(leader, m, points=5)
            ReputationEvent.objects.filter(prediction=prediction).update(created_at=since)

        finalize_weekly_contest(week_code)
        response = self.client.get(reverse("dashboard:weekly_contest"))
        self.assertContains(response, "Past winners")
        self.assertContains(response, leader.public_name)

        response_week = self.client.get(
            reverse("dashboard:weekly_contest"),
            {"week": week_code},
        )
        self.assertContains(response_week, "Week winners")
        self.assertContains(response_week, leader.public_name)

    @override_settings(WEEKLY_CONTEST_ENABLED=False)
    def test_weekly_contest_disabled_returns_404(self):
        response = self.client.get(reverse("dashboard:weekly_contest"))
        self.assertEqual(response.status_code, 404)


@override_settings(WEEKLY_CONTEST_ENABLED=True)
class WeeklyContestLoginAnnouncementTests(TestCase):
    def setUp(self):
        self.user = create_user("wcannounce")

    def test_announcement_modal_shows_once_after_login_queue(self):
        from reputation.weekly_contest_services import WEEKLY_CONTEST_ANNOUNCEMENT_SESSION_KEY

        session = self.client.session
        session[WEEKLY_CONTEST_ANNOUNCEMENT_SESSION_KEY] = True
        session.save()
        self.client.force_login(self.user)

        response = self.client.get(reverse("dashboard:reputation_leaderboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "weekly-contest-modal-title")
        self.assertContains(response, "View standings")

        response2 = self.client.get(reverse("dashboard:reputation_leaderboard"))
        self.assertNotContains(response2, "weekly-contest-modal-title")

    def test_dismiss_prevents_future_announcements(self):
        from reputation.weekly_contest_services import (
            WEEKLY_CONTEST_ANNOUNCEMENT_SESSION_KEY,
            dismiss_weekly_contest_announcement,
            queue_weekly_contest_announcement,
        )

        dismiss_weekly_contest_announcement(user=self.user)
        session = self.client.session
        queue_weekly_contest_announcement(
            request=type("Req", (), {"user": self.user, "session": session})()
        )
        self.assertNotIn(WEEKLY_CONTEST_ANNOUNCEMENT_SESSION_KEY, session)

        session[WEEKLY_CONTEST_ANNOUNCEMENT_SESSION_KEY] = True
        session.save()
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard:reputation_leaderboard"))
        self.assertNotContains(response, "weekly-contest-modal-title")

    def test_dismiss_announcement_endpoint(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("dashboard:weekly_contest_dismiss_announcement"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"ok": True})

    def test_announcement_modal_renders_in_spanish(self):
        from reputation.weekly_contest_services import WEEKLY_CONTEST_ANNOUNCEMENT_SESSION_KEY

        session = self.client.session
        session[WEEKLY_CONTEST_ANNOUNCEMENT_SESSION_KEY] = True
        session.save()
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("dashboard:reputation_leaderboard"),
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Concurso semanal")
        self.assertContains(response, "Ver clasificación")
        self.assertNotContains(response, "View standings")
