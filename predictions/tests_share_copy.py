"""Tests for resolved vs open forecast share copy."""

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

    def test_correct_resolution_uses_i_told_you_so(self):
        self.prediction.status = Prediction.Status.RESOLVED
        self.prediction.is_correct = True
        self.prediction.resolved_at = timezone.now()
        self.prediction.save(update_fields=["status", "is_correct", "resolved_at"])

        copy = get_forecast_share_copy(self.prediction)

        self.assertEqual(copy["tone"], "win")
        self.assertIn("I told you so", copy["text"])
        self.assertEqual(copy["button_label"], "I told you so")

    def test_incorrect_resolution_uses_you_were_right(self):
        self.prediction.status = Prediction.Status.RESOLVED
        self.prediction.is_correct = False
        self.prediction.resolved_at = timezone.now()
        self.prediction.save(update_fields=["status", "is_correct", "resolved_at"])

        copy = get_forecast_share_copy(self.prediction)

        self.assertEqual(copy["tone"], "loss")
        self.assertIn("You were right", copy["text"])
        self.assertIn(":(", copy["text"])
        self.assertEqual(copy["button_label"], "You were right :(")

    @override("es")
    def test_spanish_win_copy(self):
        self.prediction.status = Prediction.Status.RESOLVED
        self.prediction.is_correct = True
        self.prediction.resolved_at = timezone.now()
        self.prediction.save(update_fields=["status", "is_correct", "resolved_at"])

        copy = get_forecast_share_copy(self.prediction)

        self.assertEqual(copy["button_label"], "Te lo dije")
        self.assertIn("Te lo dije", copy["text"])

    @override("es")
    def test_spanish_loss_copy(self):
        self.prediction.status = Prediction.Status.RESOLVED
        self.prediction.is_correct = False
        self.prediction.resolved_at = timezone.now()
        self.prediction.save(update_fields=["status", "is_correct", "resolved_at"])

        copy = get_forecast_share_copy(self.prediction)

        self.assertEqual(copy["button_label"], "Tenías razón :(")
        self.assertIn("Tenías razón", copy["text"])

    def test_resolved_card_page_shows_win_button(self):
        self.prediction.status = Prediction.Status.RESOLVED
        self.prediction.is_correct = True
        self.prediction.resolved_at = timezone.now()
        self.prediction.save(update_fields=["status", "is_correct", "resolved_at"])

        response = self.client.get(
            reverse("prediction_card", args=[self.prediction.id]),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "I told you so")
        self.assertContains(response, "data-share-text")
