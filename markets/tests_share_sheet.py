from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from markets.models import Market


class MarketShareSheetTests(TestCase):
    def setUp(self):
        self.market = Market.objects.create(
            external_id="share-sheet-market",
            title="Will AI win the debate?",
            slug="share-sheet-market",
            status=Market.Status.OPEN,
            accepting_orders=True,
            close_date=timezone.now() + timedelta(days=30),
        )

    def test_market_detail_includes_share_button(self):
        response = self.client.get(reverse("markets:detail", kwargs={"slug": self.market.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "openShareSheetFromButton")
        self.assertContains(response, "data-share-url")
        self.assertContains(response, "share-sheet.js")

    @override_settings(LANGUAGE_CODE="es")
    def test_market_detail_share_button_renders_spanish(self):
        response = self.client.get(
            reverse("markets:detail", kwargs={"slug": self.market.slug}),
            HTTP_ACCEPT_LANGUAGE="es",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Compartir")
        self.assertContains(response, "share-sheet.js")
