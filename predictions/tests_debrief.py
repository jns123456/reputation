"""Tests for forecast debriefs (post-resolution reflections)."""

from django.test import TestCase, override_settings
from django.urls import reverse

from comments.models import Vote
from comments.services import cast_vote
from conftest import create_market, create_user
from predictions.debrief_services import (
    DEBRIEF_MIN_CHARS,
    DebriefError,
    create_forecast_debrief,
)
from predictions.models import ForecastDebrief, Prediction
from predictions.services import create_prediction, resolve_market_predictions
from reputation.models import PopularityEvent
from markets.models import Market


def _resolve_forecast(*, user, market, outcome="Yes"):
    prediction = create_prediction(
        user=user,
        market=market,
        predicted_outcome=outcome,
    )
    market.status = Market.Status.RESOLVED
    market.resolved_outcome = outcome
    market.save(update_fields=["status", "resolved_outcome", "updated_at"])
    resolve_market_predictions(market)
    prediction.refresh_from_db()
    return prediction


class ForecastDebriefServiceTests(TestCase):
    def setUp(self):
        self.user = create_user("debriefer")
        self.other = create_user("voter")
        self.market = create_market(
            external_id="debrief-m1",
            slug="debrief-market",
            title="Will debriefs ship?",
        )

    def test_create_debrief_after_resolution(self):
        prediction = _resolve_forecast(user=self.user, market=self.market)
        body = "I underweighted the consensus shift after the debate."
        debrief = create_forecast_debrief(
            prediction=prediction,
            user=self.user,
            body=body,
        )
        self.assertEqual(debrief.body, body)
        self.assertEqual(debrief.user_id, self.user.id)
        self.assertTrue(
            PopularityEvent.objects.filter(
                user=self.user,
                prediction=prediction,
                event_type=PopularityEvent.EventType.DEBRIEF_POSTED,
                points_delta=0,
            ).exists()
        )

    def test_cannot_debrief_pending_forecast(self):
        prediction = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
        )
        with self.assertRaises(DebriefError):
            create_forecast_debrief(
                prediction=prediction,
                user=self.user,
                body="x" * DEBRIEF_MIN_CHARS,
            )

    def test_cannot_debrief_someone_elses_forecast(self):
        prediction = _resolve_forecast(user=self.user, market=self.market)
        with self.assertRaises(DebriefError):
            create_forecast_debrief(
                prediction=prediction,
                user=self.other,
                body="x" * DEBRIEF_MIN_CHARS,
            )

    def test_debrief_is_write_once(self):
        prediction = _resolve_forecast(user=self.user, market=self.market)
        create_forecast_debrief(
            prediction=prediction,
            user=self.user,
            body="First take on what I missed in the priors.",
        )
        with self.assertRaises(DebriefError):
            create_forecast_debrief(
                prediction=prediction,
                user=self.user,
                body="Trying to edit by posting again should fail.",
            )
        self.assertEqual(ForecastDebrief.objects.filter(prediction=prediction).count(), 1)

    def test_debrief_too_short_rejected(self):
        prediction = _resolve_forecast(user=self.user, market=self.market)
        with self.assertRaises(DebriefError):
            create_forecast_debrief(
                prediction=prediction,
                user=self.user,
                body="too short",
            )

    def test_vote_on_debrief_affects_popularity_only(self):
        prediction = _resolve_forecast(user=self.user, market=self.market)
        debrief = create_forecast_debrief(
            prediction=prediction,
            user=self.user,
            body="Wrong on timing — news flow was faster than I modeled.",
        )
        self.user.profile.refresh_from_db()
        before_rep = self.user.profile.reputation_points
        before_pop = self.user.profile.popularity_points

        cast_vote(
            user=self.other,
            target_type=Vote.TargetType.DEBRIEF,
            target_id=debrief.id,
            value=1,
        )
        self.user.profile.refresh_from_db()
        debrief.refresh_from_db()

        self.assertEqual(self.user.profile.reputation_points, before_rep)
        self.assertGreater(self.user.profile.popularity_points, before_pop)
        self.assertGreater(debrief.popularity_score, 0)

    def test_cannot_vote_own_debrief(self):
        prediction = _resolve_forecast(user=self.user, market=self.market)
        debrief = create_forecast_debrief(
            prediction=prediction,
            user=self.user,
            body="Solid call on the base rate; I would size the same again.",
        )
        with self.assertRaises(ValueError):
            cast_vote(
                user=self.user,
                target_type=Vote.TargetType.DEBRIEF,
                target_id=debrief.id,
                value=1,
            )


class ForecastDebriefViewTests(TestCase):
    def setUp(self):
        self.user = create_user("writer")
        self.market = create_market(
            external_id="debrief-v1",
            slug="debrief-view-market",
            title="View debrief market",
        )
        self.prediction = _resolve_forecast(user=self.user, market=self.market)
        self.url = reverse(
            "predictions:create_debrief",
            kwargs={"prediction_id": self.prediction.id},
        )

    def test_post_creates_debrief_and_renders_partial(self):
        self.client.force_login(self.user)
        body = "The market moved on liquidity, not new information."
        response = self.client.post(
            self.url,
            {"body": body},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Debrief")
        self.assertContains(response, body)
        self.assertTrue(
            ForecastDebrief.objects.filter(prediction=self.prediction).exists()
        )

    def test_market_detail_shows_composer_for_owner(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("markets:detail", kwargs={"slug": self.market.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Write your debrief")
        self.assertContains(response, f'id="debrief-{self.prediction.id}"')

    @override_settings(LANGUAGE_CODE="es")
    def test_market_detail_debrief_spanish(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("markets:detail", kwargs={"slug": self.market.slug}),
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Escribe tu debrief")
        self.assertContains(response, f'id="debrief-{self.prediction.id}"')

    def test_resolved_notification_links_to_debrief_anchor(self):
        from accounts.models import Notification

        notification = Notification.objects.filter(
            recipient=self.user,
            notification_type=Notification.NotificationType.PREDICTION_RESOLVED,
            prediction=self.prediction,
        ).first()
        self.assertIsNotNone(notification)
        self.assertTrue(notification.action_url.endswith(f"#debrief-{self.prediction.id}"))
        self.assertEqual(notification.action_label, "Write your debrief")
