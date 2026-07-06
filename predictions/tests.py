from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from accounts.selectors import get_user_prediction_history
from comments.models import Comment, Vote
from comments.services import cast_vote
from conftest import create_user
from markets.models import Market
from predictions.models import Prediction
from predictions.selectors import (
    attach_user_forecasts_to_markets,
    clear_forecasts_market_options_cache,
    get_forecasts_market_options,
    get_market_predictions,
    get_user_active_prediction,
    get_user_closed_prediction_history,
    get_user_open_predictions,
    get_user_prediction_summary,
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
        self.assertEqual(self.user.profile.scored_forecast_count, 1)
        self.assertEqual(self.user.profile.correct_prediction_count, 1)
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
        self.assertEqual(self.user.profile.scored_forecast_count, 1)
        self.assertEqual(self.user.profile.correct_prediction_count, 0)
        self.assertEqual(self.user.profile.incorrect_prediction_count, 1)

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


class PredictionSummaryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="summary-user", password="pass")
        self.market = Market.objects.create(
            external_id="summary-m1",
            title="Summary test",
            slug="summary-test",
            source=Market.Source.MANUAL,
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )

    def test_open_forecasts_do_not_affect_accuracy(self):
        create_prediction(user=self.user, market=self.market, predicted_outcome="Yes")
        summary = get_user_prediction_summary(self.user)
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["open"], 1)
        self.assertEqual(summary["correct"], 0)
        self.assertEqual(summary["incorrect"], 0)
        self.assertIsNone(summary["accuracy_pct"])

    def test_resolved_forecasts_compute_accuracy(self):
        prediction = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
        )
        self.market.status = Market.Status.RESOLVED
        self.market.resolved_outcome = "Yes"
        self.market.save()
        resolve_market_predictions(self.market)
        prediction.refresh_from_db()

        summary = get_user_prediction_summary(self.user)
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["open"], 0)
        self.assertEqual(summary["correct"], 1)
        self.assertEqual(summary["incorrect"], 0)
        self.assertEqual(summary["accuracy_pct"], 100)


class ClosedPredictionHistoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="history-user", password="pass")
        self.market = Market.objects.create(
            external_id="history-m1",
            title="History test",
            slug="history-test",
            source=Market.Source.MANUAL,
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.4, "No": 0.6},
        )

    def test_closed_history_excludes_pending_forecasts(self):
        pending_market = Market.objects.create(
            external_id="history-m0",
            title="Still open",
            slug="still-open",
            source=Market.Source.MANUAL,
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.4, "No": 0.6},
        )
        create_prediction(
            user=self.user,
            market=pending_market,
            predicted_outcome="Yes",
        )

        to_exit = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
        )
        self.market.current_probability = {"Yes": 0.55, "No": 0.45}
        self.market.save(update_fields=["current_probability"])
        exited = exit_prediction(prediction=to_exit, user=self.user)

        resolved_market = Market.objects.create(
            external_id="history-m2",
            title="Resolved market",
            slug="resolved-market",
            source=Market.Source.MANUAL,
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )
        resolved_prediction = create_prediction(
            user=self.user,
            market=resolved_market,
            predicted_outcome="Yes",
        )
        resolved_market.status = Market.Status.RESOLVED
        resolved_market.resolved_outcome = "Yes"
        resolved_market.save()
        resolve_market_predictions(resolved_market)
        resolved_prediction.refresh_from_db()

        closed = list(get_user_closed_prediction_history(self.user))
        self.assertEqual(len(closed), 2)
        self.assertEqual({item.id for item in closed}, {exited.id, resolved_prediction.id})

    def test_closed_history_status_filter(self):
        prediction = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
        )
        self.market.current_probability = {"Yes": 0.55, "No": 0.45}
        self.market.save(update_fields=["current_probability"])
        exit_prediction(prediction=prediction, user=self.user)

        self.assertEqual(len(get_user_closed_prediction_history(self.user)), 1)
        self.assertEqual(
            len(get_user_closed_prediction_history(self.user, status=Prediction.Status.EXITED)),
            1,
        )
        self.assertEqual(
            len(get_user_closed_prediction_history(self.user, status=Prediction.Status.RESOLVED)),
            0,
        )

    def test_history_page_is_public_and_shows_closed_only(self):
        create_prediction(user=self.user, market=self.market, predicted_outcome="Yes")
        self.market.current_probability = {"Yes": 0.55, "No": 0.45}
        self.market.save(update_fields=["current_probability"])
        exit_prediction(
            prediction=Prediction.objects.filter(user=self.user).first(),
            user=self.user,
        )

        url = reverse("predictions:history", kwargs={"username": self.user.username})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "History test")
        self.assertNotContains(response, "Pending")

        filtered = self.client.get(f"{url}?status=exited")
        self.assertEqual(filtered.status_code, 200)
        self.assertContains(filtered, "History test")


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
        self.assertContains(response, "+60")
        self.assertContains(response, "-40")
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

    def test_exit_from_open_predictions_shows_error_on_closed_market(self):
        self.market.status = Market.Status.CLOSED
        self.market.save(update_fields=["status"])
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "predictions:exit",
                kwargs={"slug": self.market.slug, "prediction_id": self.prediction.id},
            ),
            {"source": "open_predictions"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 422)
        self.assertContains(
            response,
            "Cannot exit a forecast after the market has closed.",
            status_code=422,
        )
        self.prediction.refresh_from_db()
        self.assertEqual(self.prediction.status, Prediction.Status.PENDING)


class AttachUserForecastsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="forecaster", password="pass")
        self.other = User.objects.create_user(username="other", password="pass")
        self.forecasted_market = Market.objects.create(
            external_id="attach-m1",
            title="Forecasted market",
            slug="forecasted-market",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )
        self.open_market = Market.objects.create(
            external_id="attach-m2",
            title="Open market",
            slug="open-market",
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.5, "No": 0.5},
        )
        self.forecast = create_prediction(
            user=self.user,
            market=self.forecasted_market,
            predicted_outcome="Yes",
        )

    def test_attach_user_forecasts_marks_markets_with_pending_prediction(self):
        markets = attach_user_forecasts_to_markets(
            self.user,
            [self.forecasted_market, self.open_market],
        )

        self.assertIsNotNone(markets[0].user_forecast)
        self.assertEqual(markets[0].user_forecast.market_id, self.forecasted_market.id)
        self.assertIsNone(markets[1].user_forecast)

    def test_attach_user_forecasts_clears_for_anonymous_user(self):
        markets = attach_user_forecasts_to_markets(
            AnonymousUser(),
            [self.forecasted_market],
        )

        self.assertIsNone(markets[0].user_forecast)


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
        message = str(ctx.exception).lower()
        self.assertTrue(
            "already closed" in message or "already started" in message,
            msg=message,
        )
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

        self.assertFalse(market.is_forecastable)
        self.assertFalse(market.is_exitable)

        with self.assertRaises(ValueError) as ctx:
            exit_prediction(prediction=prediction, user=self.user)
        message = str(ctx.exception).lower()
        self.assertIn("started", message)

    def test_exit_allowed_when_source_stopped_accepting_orders(self):
        market = self._market(
            close_date=timezone.now() + timedelta(hours=3),
            slug="exit-not-accepting-orders",
        )
        prediction = create_prediction(
            user=self.user,
            market=market,
            predicted_outcome="Yes",
        )
        market.accepting_orders = False
        market.save(update_fields=["accepting_orders"])

        self.assertFalse(market.is_forecastable)
        self.assertTrue(market.is_exitable)

        exited = exit_prediction(prediction=prediction, user=self.user)
        self.assertEqual(exited.status, Prediction.Status.EXITED)

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

    def test_exit_blocked_once_event_started(self):
        market = self._market(
            close_date=timezone.now() + timedelta(hours=4),
            slug="event-in-play-exit",
        )
        prediction = create_prediction(
            user=self.user,
            market=market,
            predicted_outcome="Yes",
        )
        market.game_start_time = timezone.now() - timedelta(minutes=10)
        market.save(update_fields=["game_start_time"])

        self.assertTrue(market.is_in_play)
        self.assertFalse(market.is_exitable)

        with self.assertRaises(ValueError) as ctx:
            exit_prediction(prediction=prediction, user=self.user)
        self.assertIn("event has started", str(ctx.exception).lower())

    def test_forecastable_before_event_starts(self):
        market = self._market(
            close_date=timezone.now() + timedelta(hours=4),
            slug="event-not-started",
        )
        market.game_start_time = timezone.now() + timedelta(hours=2)
        market.save(update_fields=["game_start_time"])

        self.assertFalse(market.is_in_play)
        self.assertTrue(market.is_forecastable)


class ForecastMarketOptionsCacheTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username="options-user", password="pass")
        self.market = Market.objects.create(
            external_id="options-market",
            title="Options market",
            slug="options-market",
            status=Market.Status.OPEN,
        )
        Prediction.objects.create(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
            probability_at_prediction_time={"Yes": 0.5},
        )

    def test_forecasts_market_options_are_cached(self):
        with self.assertNumQueries(1):
            options = get_forecasts_market_options()
        self.assertEqual([market.slug for market in options], ["options-market"])

        with self.assertNumQueries(0):
            cached_options = get_forecasts_market_options()
        self.assertEqual([market.slug for market in cached_options], ["options-market"])

    def test_forecasts_market_options_cache_can_be_cleared(self):
        get_forecasts_market_options()

        clear_forecasts_market_options_cache()

        with self.assertNumQueries(1):
            get_forecasts_market_options()


class GuestForecastAccessTests(TestCase):
    def setUp(self):
        self.market = Market.objects.create(
            external_id="guest-forecast-m1",
            title="Guest forecast market",
            slug="guest-forecast-market",
            status=Market.Status.OPEN,
            accepting_orders=True,
            close_date=timezone.now() + timedelta(days=3),
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.4, "No": 0.6},
        )

    def test_anonymous_market_detail_shows_forecast_form(self):
        response = self.client.get(
            reverse("markets:detail", kwargs={"slug": self.market.slug})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="place-forecast"')
        self.assertContains(response, "Post forecast")
        self.assertContains(response, "openAuthModal")
        self.assertNotContains(response, "to place your forecast on this market")

    def test_anonymous_market_detail_includes_auth_modal(self):
        response = self.client.get(
            reverse("markets:detail", kwargs={"slug": self.market.slug})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pr-auth-modal")
        self.assertContains(response, "auth-modal.js")

    def test_anonymous_market_detail_auth_modal_renders_spanish(self):
        response = self.client.get(
            reverse("markets:detail", kwargs={"slug": self.market.slug}),
            HTTP_ACCEPT_LANGUAGE="es",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Crear cuenta")
        self.assertContains(response, "Crea una cuenta para publicar tu pronóstico en este evento.")


class MarketReturnNavigationTests(TestCase):
    def setUp(self):
        self.user = create_user(username="return-nav-user")
        self.market = Market.objects.create(
            external_id="return-nav-m1",
            title="Return navigation market",
            slug="return-navigation-market",
            status=Market.Status.OPEN,
            accepting_orders=True,
            close_date=timezone.now() + timedelta(days=2),
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.4, "No": 0.6},
        )
        self.client.force_login(self.user)

    def test_market_detail_remembers_referer_for_back_navigation(self):
        referer = reverse("markets:list")
        absolute_referer = self.client.request().wsgi_request.build_absolute_uri(referer)
        response = self.client.get(
            reverse("markets:detail", kwargs={"slug": self.market.slug}),
            HTTP_REFERER=absolute_referer,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'name="next" value="{absolute_referer}"')

    def test_successful_forecast_redirect_includes_posted_flag(self):
        list_url = reverse("markets:list")
        self.client.get(
            reverse("markets:detail", kwargs={"slug": self.market.slug}),
            HTTP_REFERER=self.client.request().wsgi_request.build_absolute_uri(list_url),
        )

        response = self.client.post(
            reverse("predictions:create", kwargs={"slug": self.market.slug}),
            {"predicted_outcome": "Yes", "next": list_url},
        )

        prediction = Prediction.objects.get(user=self.user, market=self.market)
        self.assertRedirects(
            response,
            (
                f"{reverse('markets:detail', kwargs={'slug': self.market.slug})}"
                f"?posted=1&share_forecast={prediction.id}#forecasts"
            ),
            fetch_redirect_response=False,
        )

    def test_back_link_shown_after_forecast(self):
        list_url = reverse("markets:list")
        self.client.get(
            reverse("markets:detail", kwargs={"slug": self.market.slug}),
            HTTP_REFERER=self.client.request().wsgi_request.build_absolute_uri(list_url),
        )
        self.client.post(
            reverse("predictions:create", kwargs={"slug": self.market.slug}),
            {"predicted_outcome": "Yes", "next": list_url},
        )

        response = self.client.get(
            reverse("markets:detail", kwargs={"slug": self.market.slug}),
        )

        self.assertContains(response, f'href="{list_url}"')
        self.assertContains(response, "← Back")
