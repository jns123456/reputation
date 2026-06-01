from django.test import TestCase, override_settings

from markets.display_metadata import (
    extract_card_image_url_from_market,
    extract_volume_total_from_market,
    format_volume_label,
    sync_market_display_metadata,
)
from markets.models import Market


class DisplayMetadataTests(TestCase):
    def test_format_volume_label(self):
        self.assertEqual(format_volume_label(2_500_000), "$2.5M Vol.")
        self.assertEqual(format_volume_label(12_000), "$12K Vol.")
        self.assertEqual(format_volume_label(500), "$500 Vol.")
        self.assertEqual(format_volume_label(0), "")

    def test_extract_volume_from_polymarket_raw(self):
        market = Market(
            external_id="meta-vol",
            title="Volume test",
            slug="volume-test",
            polymarket_raw={"volumeNum": 5000},
        )
        self.assertEqual(extract_volume_total_from_market(market), 5000.0)

    def test_extract_image_from_polymarket_raw(self):
        market = Market(
            external_id="meta-img",
            title="Image test",
            slug="image-test",
            polymarket_raw={"image": "https://example.com/market.png"},
        )
        self.assertEqual(
            extract_card_image_url_from_market(market),
            "https://example.com/market.png",
        )

    def test_sync_persists_denormalized_fields(self):
        market = Market.objects.create(
            external_id="meta-sync",
            title="Sync test",
            slug="sync-test",
            polymarket_raw={"volumeNum": 9000, "image": "https://example.com/sync.png"},
        )
        sync_market_display_metadata(market, save=True)
        market.refresh_from_db()
        self.assertEqual(market.volume_total, 9000.0)
        self.assertEqual(market.card_image_url, "https://example.com/sync.png")

    def test_image_url_uses_stored_field_without_raw_json(self):
        market = Market.objects.create(
            external_id="meta-stored-img",
            title="Stored image",
            slug="stored-image",
            card_image_url="https://example.com/stored.png",
        )
        self.assertEqual(market.image_url, "https://example.com/stored.png")

    def test_volume_label_uses_stored_total_without_raw_json(self):
        market = Market.objects.create(
            external_id="meta-stored-vol",
            title="Stored volume",
            slug="stored-volume",
            volume_total=1_500_000,
        )
        self.assertEqual(market.volume_label, "$1.5M Vol.")


@override_settings(WORLD_CUP_MATCHES_PER_PAGE=2)
class WorldCupPaginationTests(TestCase):
    def setUp(self):
        for index in range(5):
            Market.objects.create(
                external_id=f"wc-match:wc-page-{index}",
                title=f"Match {index}",
                slug=f"match-{index}",
                status=Market.Status.OPEN,
                polymarket_raw={"market_kind": "soccer_match_3way"},
                polymarket_event_raw={"tags": [{"slug": "fifa-world-cup"}]},
                volume_total=float(index),
            )

    def test_world_cup_page_one_shows_limited_matches(self):
        from django.urls import reverse

        response = self.client.get(
            reverse("dashboard:category_browse", kwargs={"slug": "sports"}),
            {"area": "world-cup-games"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["markets"]), 2)
        self.assertEqual(response.context["market_count"], 5)
        self.assertTrue(response.context["page_obj"].has_next)
        self.assertTrue(response.context["world_cup_match_layout"])

    def test_world_cup_page_two(self):
        from django.urls import reverse

        response = self.client.get(
            reverse("dashboard:category_browse", kwargs={"slug": "sports"}),
            {"area": "world-cup-games", "page": 2},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["markets"]), 2)
        self.assertEqual(response.context["page_obj"].number, 2)

    def test_legacy_world_cup_url_redirects_to_sports_sub_area(self):
        from django.urls import reverse

        response = self.client.get(
            reverse("dashboard:category_browse", kwargs={"slug": "fifa-world-cup-2026"})
        )
        self.assertRedirects(
            response,
            reverse("dashboard:category_browse", kwargs={"slug": "sports"})
            + "?area=world-cup-games",
            fetch_redirect_response=False,
        )
