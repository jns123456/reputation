"""Public prediction card pages, OG images, and share popularity."""

from django.test import TestCase
from django.urls import reverse

from conftest import create_market, create_user
from predictions.services import create_prediction
from reputation.models import PopularityEvent


class PredictionCardTests(TestCase):
    def setUp(self):
        self.author = create_user("cardauthor")
        self.market = create_market(
            external_id="card-mkt",
            slug="card-mkt",
        )
        self.prediction = create_prediction(
            user=self.author,
            market=self.market,
            predicted_outcome="Yes",
        )

    def test_card_page_renders_for_anonymous_visitor(self):
        response = self.client.get(reverse("prediction_card", args=[self.prediction.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.market.display_title)

    def test_card_page_renders_in_spanish(self):
        response = self.client.get(
            reverse("prediction_card", args=[self.prediction.id]),
            HTTP_ACCEPT_LANGUAGE="es",
        )
        self.assertEqual(response.status_code, 200)

    def test_og_image_returns_png(self):
        response = self.client.get(reverse("prediction_card_og", args=[self.prediction.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response.content[:8], b"\x89PNG\r\n\x1a\n")

    def test_share_awards_popularity_once_per_viewer(self):
        viewer = create_user("cardviewer")
        self.client.force_login(viewer)
        url = reverse("prediction_card_share", args=[self.prediction.id])

        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["recorded"])

        # Second click from the same viewer is deduped.
        response = self.client.post(url)
        self.assertFalse(response.json()["recorded"])

        events = PopularityEvent.objects.filter(
            user=self.author,
            event_type=PopularityEvent.EventType.SHARE_RECEIVED,
        )
        self.assertEqual(events.count(), 1)
        self.assertEqual(events.first().points_delta, 1)

    def test_self_share_awards_nothing(self):
        self.client.force_login(self.author)
        response = self.client.post(
            reverse("prediction_card_share", args=[self.prediction.id])
        )
        self.assertFalse(response.json()["recorded"])
        self.assertEqual(
            PopularityEvent.objects.filter(
                event_type=PopularityEvent.EventType.SHARE_RECEIVED
            ).count(),
            0,
        )

    def test_anonymous_share_records_nothing_but_does_not_error(self):
        response = self.client.post(
            reverse("prediction_card_share", args=[self.prediction.id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["recorded"])
