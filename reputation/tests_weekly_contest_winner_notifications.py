"""Weekly contest winner email and login modal notifications."""

from unittest.mock import patch

from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from conftest import create_market, create_user
from predictions.models import Prediction
from reputation.models import ReputationEvent, WeeklyContestWinner
from reputation.weekly_contest_winner_notifications import (
    WEEKLY_CONTEST_WIN_PENDING_CACHE,
    WEEKLY_CONTEST_WIN_SESSION_KEY,
    notify_weekly_contest_winners,
    user_has_pending_weekly_contest_win,
)
from reputation.weekly_contest_services import (
    WEEKLY_CONTEST_ANNOUNCEMENT_SESSION_KEY,
    finalize_weekly_contest,
    week_date_range,
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
        reason="winner notification test",
    )
    return prediction


@override_settings(WEEKLY_CONTEST_ENABLED=True, WEEKLY_CONTEST_WINNER_EMAILS_ENABLED=True)
class WeeklyContestWinnerNotificationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.market = create_market(external_id="wn1", slug="wn1")
        self.winner = create_user("weeklywinner")

    @patch("reputation.weekly_contest_winner_notifications.send_weekly_contest_winner_email")
    @override_settings(WEEKLY_CONTEST_FIRST_WEEK_START="2020-01-01")
    def test_finalize_notifies_new_winners(self, mock_send_email):
        week_code = "2020-03-08"
        since, _until = week_date_range(week_code)
        for index in range(12):
            market = create_market(external_id=f"wn-{index}", slug=f"wn-{index}")
            prediction = _scored_prediction(self.winner, market, points=50)
            ReputationEvent.objects.filter(prediction=prediction).update(created_at=since)

        created = finalize_weekly_contest(week_code)

        self.assertEqual(created, 2)
        win = WeeklyContestWinner.objects.filter(user=self.winner, week_code=week_code).first()
        self.assertIsNotNone(win.notified_at)
        self.assertEqual(mock_send_email.call_count, 2)
        self.assertTrue(user_has_pending_weekly_contest_win(self.winner))

    @patch("reputation.weekly_contest_winner_notifications.send_weekly_contest_winner_email")
    def test_notify_is_idempotent(self, mock_send_email):
        win = WeeklyContestWinner.objects.create(
            user=self.winner,
            week_code="2020-01-05",
            prize_type=WeeklyContestWinner.PrizeType.ABSOLUTE,
            prize_usd=5,
        )
        self.assertEqual(notify_weekly_contest_winners([win]), 1)
        win.refresh_from_db()
        first_notified = win.notified_at
        self.assertEqual(notify_weekly_contest_winners([win]), 0)
        win.refresh_from_db()
        self.assertEqual(win.notified_at, first_notified)
        mock_send_email.assert_called_once()

    @patch("reputation.weekly_contest_winner_notifications.send_weekly_contest_winner_email")
    def test_login_shows_winner_modal_once(self, _mock_send_email):
        win = WeeklyContestWinner.objects.create(
            user=self.winner,
            week_code="2020-01-05",
            prize_type=WeeklyContestWinner.PrizeType.ABSOLUTE,
            prize_usd=5,
        )
        notify_weekly_contest_winners([win])

        client = Client()
        client.force_login(self.winner)

        response = client.get(reverse("dashboard:reputation_leaderboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "weekly-contest-win-modal-title")
        self.assertContains(response, "Prize credited")
        self.assertNotContains(response, "weekly-contest-modal-title")

        response2 = client.get(reverse("dashboard:reputation_leaderboard"))
        self.assertNotContains(response2, "weekly-contest-win-modal-title")

    def test_win_modal_suppresses_contest_announcement(self):
        win = WeeklyContestWinner.objects.create(
            user=self.winner,
            week_code="2020-01-05",
            prize_type=WeeklyContestWinner.PrizeType.ABSOLUTE,
            prize_usd=5,
        )
        cache.set(
            WEEKLY_CONTEST_WIN_PENDING_CACHE.format(user_id=self.winner.id),
            [win.id],
            timeout=60,
        )

        client = Client()
        session = client.session
        session[WEEKLY_CONTEST_ANNOUNCEMENT_SESSION_KEY] = True
        session.save()
        client.force_login(self.winner)

        response = client.get(reverse("dashboard:reputation_leaderboard"))
        self.assertContains(response, "weekly-contest-win-modal-title")
        self.assertNotContains(response, "weekly-contest-modal-title")

    @patch("accounts.email_services._send")
    def test_winner_email_renders(self, mock_send):
        win = WeeklyContestWinner.objects.create(
            user=self.winner,
            week_code="2020-01-05",
            prize_type=WeeklyContestWinner.PrizeType.RELATIVE,
            prize_usd=5,
        )
        from reputation.weekly_contest_winner_notifications import send_weekly_contest_winner_email

        self.assertTrue(send_weekly_contest_winner_email(win=win))
        mock_send.assert_called_once()
        self.assertEqual(mock_send.call_args.kwargs["template_base"], "weekly_contest_winner")

    def test_spanish_winner_modal_renders(self):
        win = WeeklyContestWinner.objects.create(
            user=self.winner,
            week_code="2020-01-05",
            prize_type=WeeklyContestWinner.PrizeType.ABSOLUTE,
            prize_usd=5,
            notified_at=timezone.now(),
        )
        client = Client()
        client.force_login(self.winner)
        session = client.session
        session[WEEKLY_CONTEST_WIN_SESSION_KEY] = [win.id]
        session.save()

        response = client.get(
            reverse("dashboard:reputation_leaderboard"),
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ganaste el concurso semanal")
