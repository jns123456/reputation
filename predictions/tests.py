from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from accounts.selectors import get_user_prediction_history
from comments.models import Comment, Vote
from comments.services import cast_vote
from markets.models import Market
from predictions.models import Prediction
from predictions.selectors import (
    get_market_predictions,
    get_user_active_prediction,
    get_user_open_predictions,
)
from predictions.services import (
    create_prediction,
    exit_prediction,
    resolve_market_predictions,
    update_prediction,
)
from predictions.forms import ForecastForm
from reputation.models import ReputationEvent
from reputation.services import apply_reputation_for_prediction_exit


class PredictionPermissionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="owner", password="pass")
        self.other = User.objects.create_user(username="other", password="pass")
        self.market = Market.objects.create(
            external_id="perm-m1",
            title="Permission test",
            slug="permission-test",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )
        self.prediction = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
        )

    def test_other_user_cannot_edit_prediction(self):
        with self.assertRaises(PermissionError):
            update_prediction(
                prediction=self.prediction,
                user=self.other,
                predicted_outcome="No",
            )

    def test_update_prediction_is_not_allowed(self):
        with self.assertRaises(ValueError):
            update_prediction(
                prediction=self.prediction,
                user=self.user,
                predicted_outcome="No",
            )

    def test_cannot_create_duplicate_forecast(self):
        with self.assertRaises(ValueError) as ctx:
            create_prediction(
                user=self.user,
                market=self.market,
                predicted_outcome="No",
            )
        self.assertIn("Only one open forecast", str(ctx.exception))

    def test_create_prediction_stores_probability_snapshot(self):
        self.market.current_probability = {"Yes": 0.35, "No": 0.65}
        self.market.save(update_fields=["current_probability"])
        prediction = create_prediction(
            user=self.other,
            market=self.market,
            predicted_outcome="Yes",
        )
        self.assertEqual(prediction.probability_at_prediction_time["Yes"], 0.35)
        self.assertEqual(prediction.probability_at_prediction_time["No"], 0.65)

    def test_create_prediction_stores_no_direction(self):
        prediction = create_prediction(
            user=self.other,
            market=self.market,
            predicted_outcome="Yes",
            predicted_direction=Prediction.Direction.NO,
        )

        self.assertEqual(prediction.predicted_outcome, "Yes")
        self.assertEqual(prediction.predicted_direction, Prediction.Direction.NO)

    def test_no_direction_resolves_correct_when_other_outcome_wins(self):
        prediction = create_prediction(
            user=self.other,
            market=self.market,
            predicted_outcome="Yes",
            predicted_direction=Prediction.Direction.NO,
        )
        self.market.status = Market.Status.RESOLVED
        self.market.resolved_outcome = "No"
        self.market.save(update_fields=["status", "resolved_outcome"])

        resolve_market_predictions(self.market)

        prediction.refresh_from_db()
        self.assertTrue(prediction.is_correct)

    def test_market_predictions_sorted_by_popularity(self):
        market = Market.objects.create(
            external_id="sort-m1",
            title="Sort test",
            slug="sort-test",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )
        low = create_prediction(
            user=self.user,
            market=market,
            predicted_outcome="Yes",
        )
        high = create_prediction(
            user=self.other,
            market=market,
            predicted_outcome="No",
        )
        voter = User.objects.create_user(username="voter", password="pass")
        cast_vote(
            user=voter,
            target_type=Vote.TargetType.PREDICTION,
            target_id=high.id,
            value=1,
        )
        high.refresh_from_db()

        ordered = list(get_market_predictions(market))
        self.assertEqual([prediction.id for prediction in ordered], [high.id, low.id])

    def test_market_predictions_tiebreak_by_author_reputation(self):
        market = Market.objects.create(
            external_id="sort-m2",
            title="Reputation tiebreak",
            slug="reputation-tiebreak",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )
        self.user.profile.reputation_score = 80.0
        self.user.profile.save(update_fields=["reputation_score"])
        self.other.profile.reputation_score = 20.0
        self.other.profile.save(update_fields=["reputation_score"])

        low_rep = create_prediction(
            user=self.other,
            market=market,
            predicted_outcome="No",
        )
        high_rep = create_prediction(
            user=self.user,
            market=market,
            predicted_outcome="Yes",
        )

        ordered = list(get_market_predictions(market))
        self.assertEqual([prediction.id for prediction in ordered], [high_rep.id, low_rep.id])

    def test_user_prediction_history_includes_interaction_counts(self):
        voter = User.objects.create_user(username="voter2", password="pass")
        cast_vote(
            user=voter,
            target_type=Vote.TargetType.PREDICTION,
            target_id=self.prediction.id,
            value=1,
        )
        disliker = User.objects.create_user(username="disliker", password="pass")
        cast_vote(
            user=disliker,
            target_type=Vote.TargetType.PREDICTION,
            target_id=self.prediction.id,
            value=-1,
        )
        Comment.objects.create(
            user=voter,
            market=self.market,
            prediction=self.prediction,
            body="Interesting take.",
        )

        prediction = get_user_prediction_history(self.user)[0]
        self.assertEqual(prediction.comment_count, 1)
        self.assertEqual(prediction.like_count, 1)
        self.assertEqual(prediction.dislike_count, 1)


class PredictionOddsRefreshTests(TestCase):
    """Forecasts must never block the request on a synchronous Polymarket fetch."""

    def setUp(self):
        self.user = User.objects.create_user(username="poly-user", password="pass")
        self.market = Market.objects.create(
            external_id="poly-refresh-1",
            title="Polymarket sourced market",
            slug="polymarket-sourced-market",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.42, "No": 0.58},
        )

    def test_create_prediction_does_not_call_polymarket_synchronously(self):
        with patch(
            "integrations.services.refresh_market_from_polymarket",
            side_effect=AssertionError("synchronous Polymarket fetch is forbidden"),
        ), patch(
            "integrations.celery_utils.enqueue_market_refresh_if_stale",
            return_value=True,
        ) as enqueue:
            prediction = create_prediction(
                user=self.user,
                market=self.market,
                predicted_outcome="Yes",
            )

        enqueue.assert_called_once()
        # Snapshot comes straight from the persisted odds, no network round-trip.
        self.assertEqual(prediction.probability_at_prediction_time, {"Yes": 0.42, "No": 0.58})


class PredictionExitTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="exiter", password="pass")
        self.other = User.objects.create_user(username="other-exiter", password="pass")
        self.market = Market.objects.create(
            external_id="exit-m1",
            title="Exit test",
            slug="exit-test",
            source=Market.Source.MANUAL,
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.4, "No": 0.6},
        )

    def test_exit_prediction_realizes_positive_delta_and_frees_slot(self):
        prediction = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
        )
        self.market.current_probability = {"Yes": 0.55, "No": 0.45}
        self.market.save(update_fields=["current_probability"])

        exited = exit_prediction(prediction=prediction, user=self.user)
        exited.refresh_from_db()
        self.user.profile.refresh_from_db()

        self.assertEqual(exited.status, Prediction.Status.EXITED)
        self.assertEqual(exited.probability_at_exit_time["Yes"], 0.55)
        self.assertEqual(self.user.profile.reputation_points, 15)
        self.assertEqual(self.user.profile.neutral_prediction_count, 0)
        self.assertEqual(self.user.profile.correct_prediction_count, 0)
        self.assertEqual(self.user.profile.incorrect_prediction_count, 0)
        self.assertIsNone(get_user_active_prediction(self.user, self.market))
        self.assertEqual(
            ReputationEvent.objects.get(prediction=exited).event_type,
            ReputationEvent.EventType.EXITED_PREDICTION,
        )

        next_prediction = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="No",
        )
        self.assertEqual(next_prediction.status, Prediction.Status.PENDING)

    def test_exit_prediction_realizes_negative_delta_for_no_side(self):
        prediction = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
            predicted_direction=Prediction.Direction.NO,
        )
        self.market.current_probability = {"Yes": 0.7, "No": 0.3}
        self.market.save(update_fields=["current_probability"])

        exit_prediction(prediction=prediction, user=self.user)
        self.user.profile.refresh_from_db()

        self.assertEqual(self.user.profile.reputation_points, -30)

    def test_other_user_cannot_exit_prediction(self):
        prediction = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
        )

        with self.assertRaises(PermissionError):
            exit_prediction(prediction=prediction, user=self.other)

    def test_cannot_exit_closed_market(self):
        prediction = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
        )
        self.market.status = Market.Status.CLOSED
        self.market.save(update_fields=["status"])

        with self.assertRaises(ValueError):
            exit_prediction(prediction=prediction, user=self.user)

    def test_exited_predictions_are_not_resolved_later(self):
        prediction = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
        )
        self.market.current_probability = {"Yes": 0.5, "No": 0.5}
        self.market.save(update_fields=["current_probability"])
        exit_prediction(prediction=prediction, user=self.user)

        self.market.status = Market.Status.RESOLVED
        self.market.resolved_outcome = "Yes"
        self.market.save(update_fields=["status", "resolved_outcome"])
        resolved = resolve_market_predictions(self.market)
        prediction.refresh_from_db()
        self.user.profile.refresh_from_db()

        self.assertEqual(resolved, [])
        self.assertEqual(prediction.status, Prediction.Status.EXITED)
        self.assertEqual(self.user.profile.reputation_points, 10)
        self.assertEqual(ReputationEvent.objects.filter(prediction=prediction).count(), 1)

    def test_exit_reputation_application_is_idempotent(self):
        prediction = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
        )
        self.market.current_probability = {"Yes": 0.55, "No": 0.45}
        self.market.save(update_fields=["current_probability"])
        exit_prediction(prediction=prediction, user=self.user)
        prediction.refresh_from_db()

        self.assertIsNone(apply_reputation_for_prediction_exit(prediction))
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.reputation_points, 15)
        self.assertEqual(ReputationEvent.objects.filter(prediction=prediction).count(), 1)


class OpenPredictionsPageTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="open-user",
            email="open-user@example.com",
            password="pass",
            onboarding_completed=True,
            email_verified_at=timezone.now(),
        )
        self.market = Market.objects.create(
            external_id="open-m1",
            title="Open forecast market",
            slug="open-forecast-market",
            source=Market.Source.MANUAL,
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.4, "No": 0.6},
        )
        self.prediction = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
            reasoning="Open position",
        )

    def test_open_predictions_selector_returns_only_pending_open_market_forecasts(self):
        closed_market = Market.objects.create(
            external_id="open-m2",
            title="Closed forecast market",
            slug="closed-forecast-market",
            source=Market.Source.MANUAL,
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )
        create_prediction(
            user=self.user,
            market=closed_market,
            predicted_outcome="Yes",
        )
        closed_market.status = Market.Status.CLOSED
        closed_market.save(update_fields=["status"])

        open_predictions = list(get_user_open_predictions(self.user))

        self.assertEqual(open_predictions, [self.prediction])

    def test_open_predictions_page_shows_unrealized_reputation_and_exit_action(self):
        self.market.current_probability = {"Yes": 0.55, "No": 0.45}
        self.market.save(update_fields=["current_probability"])
        self.client.force_login(self.user)

        response = self.client.get(reverse("predictions:open"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Open forecast market")
        self.assertContains(response, "+15")
        self.assertContains(response, reverse(
            "predictions:exit",
            kwargs={"slug": self.market.slug, "prediction_id": self.prediction.id},
        ))

    def test_open_predictions_page_requires_login(self):
        response = self.client.get(reverse("predictions:open"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response["Location"])

    def test_exit_from_open_predictions_stays_on_page_with_htmx(self):
        self.market.current_probability = {"Yes": 0.55, "No": 0.45}
        self.market.save(update_fields=["current_probability"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "predictions:exit",
                kwargs={"slug": self.market.slug, "prediction_id": self.prediction.id},
            ),
            {"source": "open_predictions"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pr-exit-success-card")
        self.assertContains(response, "+15")
        self.assertContains(response, 'id="open-count-stat"')
        self.assertContains(response, ">0<")
        self.assertContains(response, 'id="open-positions-empty"')
        self.prediction.refresh_from_db()
        self.assertEqual(self.prediction.status, Prediction.Status.EXITED)

    def test_exit_from_open_predictions_non_htmx_redirects_to_open_page(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "predictions:exit",
                kwargs={"slug": self.market.slug, "prediction_id": self.prediction.id},
            ),
            {"source": "open_predictions"},
        )

        self.assertRedirects(response, reverse("predictions:open"))


class ForecastFormTests(TestCase):
    def test_three_way_soccer_form_accepts_all_outcomes(self):
        market = Market.objects.create(
            external_id="wc-match:test",
            title="Mexico vs. South Africa",
            slug="mexico-vs-south-africa-form",
            status=Market.Status.OPEN,
            outcomes=[
                {"label": "Mexico"},
                {"label": "Draw"},
                {"label": "South Africa"},
            ],
            current_probability={"Mexico": 0.67, "Draw": 0.22, "South Africa": 0.11},
            polymarket_raw={"market_kind": "soccer_match_3way"},
        )
        form = ForecastForm(data={"predicted_outcome": "Draw"}, market=market)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["predicted_outcome"], "Draw")
        self.assertEqual(form.outcome_count, 3)

    def test_multi_outcome_form_accepts_no_direction(self):
        market = Market.objects.create(
            external_id="pm-event:test-winner",
            title="Tournament Winner",
            slug="tournament-winner-form",
            status=Market.Status.OPEN,
            outcomes=[
                {"label": "Spain"},
                {"label": "France"},
                {"label": "England"},
            ],
            current_probability={"Spain": 0.17, "France": 0.16, "England": 0.11},
            polymarket_raw={"market_kind": "polymarket_multi_outcome_event"},
        )

        form = ForecastForm(
            data={"predicted_outcome": "Spain", "predicted_direction": "no"},
            market=market,
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["predicted_direction"], "no")


class ExpiredMarketGuardTests(TestCase):
    """Guards against the Polymarket sync delay exploit.

    A market can stay ``OPEN`` locally for hours after it actually closed
    upstream. Forecasts must be blocked once ``close_date`` has passed, even if
    the imported ``status`` is still stale.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="late-bettor", password="pass")

    def _market(self, *, close_date, slug):
        return Market.objects.create(
            external_id=f"expiry-{slug}",
            title="Expiry test",
            slug=slug,
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            close_date=close_date,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )

    def test_is_forecastable_false_when_close_date_passed(self):
        market = self._market(
            close_date=timezone.now() - timedelta(hours=1),
            slug="expiry-past",
        )
        self.assertTrue(market.is_open)
        self.assertTrue(market.is_expired)
        self.assertFalse(market.is_forecastable)

    def test_is_forecastable_true_when_close_date_future(self):
        market = self._market(
            close_date=timezone.now() + timedelta(hours=1),
            slug="expiry-future",
        )
        self.assertTrue(market.is_forecastable)

    def test_is_forecastable_true_when_no_close_date(self):
        market = self._market(close_date=None, slug="expiry-none")
        self.assertTrue(market.is_forecastable)

    def test_create_prediction_blocked_on_expired_open_market(self):
        market = self._market(
            close_date=timezone.now() - timedelta(minutes=5),
            slug="expiry-create-blocked",
        )
        with self.assertRaises(ValueError) as ctx:
            create_prediction(
                user=self.user,
                market=market,
                predicted_outcome="Yes",
            )
        self.assertIn("already closed", str(ctx.exception))
        self.assertFalse(Prediction.objects.filter(market=market).exists())

    def test_forecast_form_invalid_on_expired_open_market(self):
        market = self._market(
            close_date=timezone.now() - timedelta(minutes=5),
            slug="expiry-form-blocked",
        )
        form = ForecastForm(data={"predicted_outcome": "Yes"}, market=market)
        self.assertFalse(form.is_valid())

    def test_exit_blocked_after_close_date_passes(self):
        market = self._market(
            close_date=timezone.now() + timedelta(hours=1),
            slug="expiry-exit-blocked",
        )
        prediction = create_prediction(
            user=self.user,
            market=market,
            predicted_outcome="Yes",
        )
        market.close_date = timezone.now() - timedelta(minutes=1)
        market.save(update_fields=["close_date"])

        with self.assertRaises(ValueError):
            exit_prediction(prediction=prediction, user=self.user)

    def test_not_forecastable_when_source_stopped_accepting_orders(self):
        """Replicates Polymarket: no forecasts once the source halts orders."""
        market = self._market(
            close_date=timezone.now() + timedelta(hours=3),
            slug="not-accepting-orders",
        )
        market.accepting_orders = False
        market.save(update_fields=["accepting_orders"])

        self.assertTrue(market.is_open)
        self.assertFalse(market.is_expired)
        self.assertFalse(market.is_forecastable)

        with self.assertRaises(ValueError):
            create_prediction(
                user=self.user,
                market=market,
                predicted_outcome="Yes",
            )

    def test_forecastable_while_source_accepts_orders(self):
        market = self._market(
            close_date=timezone.now() + timedelta(hours=3),
            slug="accepting-orders",
        )
        self.assertTrue(market.accepting_orders)
        self.assertTrue(market.is_forecastable)

    def test_not_forecastable_once_event_started(self):
        """Local backstop: a started match closes forecasts even if the source
        flag is stale (handles uncertain live-event end times, e.g. tennis)."""
        market = self._market(
            close_date=timezone.now() + timedelta(hours=4),
            slug="event-in-play",
        )
        market.game_start_time = timezone.now() - timedelta(minutes=10)
        market.save(update_fields=["game_start_time"])

        self.assertTrue(market.is_open)
        self.assertTrue(market.accepting_orders)
        self.assertTrue(market.is_in_play)
        self.assertFalse(market.is_forecastable)

        with self.assertRaises(ValueError) as ctx:
            create_prediction(
                user=self.user,
                market=market,
                predicted_outcome="Yes",
            )
        self.assertIn("already started", str(ctx.exception))

    def test_forecastable_before_event_starts(self):
        market = self._market(
            close_date=timezone.now() + timedelta(hours=4),
            slug="event-not-started",
        )
        market.game_start_time = timezone.now() + timedelta(hours=2)
        market.save(update_fields=["game_start_time"])

        self.assertFalse(market.is_in_play)
        self.assertTrue(market.is_forecastable)
