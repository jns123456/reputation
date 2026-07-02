"""Tests for viral prediction stamp cards and share copy."""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import override

from conftest import create_market, create_user
from predictions.models import Prediction
from predictions.services import create_prediction
from predictions.share_copy import get_forecast_share_copy


class ForecastShareCopyTests(TestCase):
    def setUp(self):
        self.user = create_user("share-copy-user")
        self.market = create_market(
            external_id="share-copy-mkt",
            slug="share-copy-mkt",
            title="Will the bill pass?",
        )
        self.prediction = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
        )

    def test_open_forecast_uses_neutral_copy(self):
        copy = get_forecast_share_copy(self.prediction)

        self.assertEqual(copy["tone"], "default")
        self.assertIn("Will the bill pass?", copy["text"])
        self.assertEqual(copy["button_label"], "Share")

    def test_correct_resolution_uses_i_called_it(self):
        self.prediction.status = Prediction.Status.RESOLVED
        self.prediction.is_correct = True
        self.prediction.resolved_at = timezone.now()
        self.prediction.save(update_fields=["status", "is_correct", "resolved_at"])

        copy = get_forecast_share_copy(
            self.prediction,
            metrics={"entry_percent": 37, "pnl_delta": 63},
        )

        self.assertEqual(copy["tone"], "win")
        self.assertIn("I called it", copy["text"])
        self.assertEqual(copy["button_label"], "I called it")

    def test_incorrect_resolution_uses_aged_badly(self):
        self.prediction.status = Prediction.Status.RESOLVED
        self.prediction.is_correct = False
        self.prediction.resolved_at = timezone.now()
        self.prediction.save(update_fields=["status", "is_correct", "resolved_at"])

        copy = get_forecast_share_copy(
            self.prediction,
            metrics={"entry_percent": 92, "pnl_delta": -92},
        )

        self.assertEqual(copy["tone"], "loss")
        self.assertIn("aged badly", copy["text"])
        self.assertEqual(copy["button_label"], "This aged badly")

    @override("es")
    def test_spanish_win_copy(self):
        self.prediction.status = Prediction.Status.RESOLVED
        self.prediction.is_correct = True
        self.prediction.resolved_at = timezone.now()
        self.prediction.save(update_fields=["status", "is_correct", "resolved_at"])

        copy = get_forecast_share_copy(self.prediction)

        self.assertIn("Lo dije", copy["button_label"])

    def test_resolved_card_page_shows_i_called_it_button(self):
        self.prediction.status = Prediction.Status.RESOLVED
        self.prediction.is_correct = True
        self.prediction.resolved_at = timezone.now()
        self.prediction.save(update_fields=["status", "is_correct", "resolved_at"])

        response = self.client.get(
            reverse("prediction_card", args=[self.prediction.id]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "I called it")
        self.assertContains(response, "PredictStamp.com")
        self.assertContains(response, "Share on X")

    def test_embed_route_renders_without_actions(self):
        response = self.client.get(
            reverse("prediction_card_embed", args=[self.prediction.id]),
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Share on X")
