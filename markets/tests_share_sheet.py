from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from conftest import create_user
from markets.models import Market
from predictions.models import Prediction
from predictions.services import create_prediction


class MarketShareSheetTests(TestCase):
    def setUp(self):
        self.market = Market.objects.create(
            external_id="share-sheet-market",
            title="Will AI win the debate?",
            slug="share-sheet-market",
            status=Market.Status.OPEN,
            accepting_orders=True,
            close_date=timezone.now() + timedelta(days=30),
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.55, "No": 0.45},
        )
        self.user = create_user(username="share-sheet-user")

    def test_market_detail_includes_event_share_button_when_logged_out(self):
        response = self.client.get(reverse("markets:detail", kwargs={"slug": self.market.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "openShareSheetFromButton")
        self.assertContains(response, reverse("markets:detail", kwargs={"slug": self.market.slug}))
        self.assertContains(response, "share-sheet.js")

    def test_market_detail_shares_forecast_card_when_user_has_forecast(self):
        prediction = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("markets:detail", kwargs={"slug": self.market.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("prediction_card", args=[prediction.id]))
        self.assertContains(response, reverse("prediction_card_share", args=[prediction.id]))
        self.assertContains(response, "Share my forecast")

    def test_posted_forecast_opens_share_sheet(self):
        prediction = create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("markets:detail", kwargs={"slug": self.market.slug}),
            {"posted": "1", "share_forecast": prediction.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="forecast-share-auto"')
        self.assertContains(response, "shareForumPost(trigger)")

    def test_share_forecast_query_ignored_for_other_users(self):
        other = create_user(username="other-share-user")
        prediction = create_prediction(
            user=other,
            market=self.market,
            predicted_outcome="Yes",
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("markets:detail", kwargs={"slug": self.market.slug}),
            {"posted": "1", "share_forecast": prediction.id},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="forecast-share-auto"')

    @override_settings(LANGUAGE_CODE="es")
    def test_market_detail_share_button_renders_spanish(self):
        response = self.client.get(
            reverse("markets:detail", kwargs={"slug": self.market.slug}),
            HTTP_ACCEPT_LANGUAGE="es",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Compartir")
        self.assertContains(response, "share-sheet.js")

    @override_settings(LANGUAGE_CODE="es")
    def test_forecast_share_button_renders_spanish(self):
        create_prediction(
            user=self.user,
            market=self.market,
            predicted_outcome="Yes",
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("markets:detail", kwargs={"slug": self.market.slug}),
            HTTP_ACCEPT_LANGUAGE="es",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Compartir mi pronóstico")
