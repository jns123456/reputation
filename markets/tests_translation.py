from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import translation

from integrations.services import import_market_from_normalized
from markets.models import Market
from markets.translation_services import apply_spanish_translations_to_defaults, translate_market_copy


@override_settings(MARKET_TRANSLATION_ENABLED=True, MARKET_TRANSLATION_REQUEST_DELAY=0)
class MarketTranslationServiceTests(TestCase):
    @patch("markets.translation_services._translate_chunk", side_effect=lambda text: f"ES:{text}")
    def test_translate_market_copy_preserves_paragraphs(self, _mock_chunk):
        translated = translate_market_copy("Line one.\n\nLine two.")
        self.assertEqual(translated, "ES:Line one.\n\nES:Line two.")

    @patch("markets.translation_services.translate_market_copy", side_effect=lambda text: f"ES:{text}")
    def test_import_populates_spanish_fields(self, _mock_translate):
        data = {
            "external_id": "translate-1",
            "title": "Will inflation fall?",
            "description": "Resolves Yes if CPI drops below 2%.",
            "category": "Economy",
            "source": "polymarket",
            "status": "open",
            "outcomes": [{"label": "Yes"}, {"label": "No"}],
            "current_probability": {"Yes": 0.4, "No": 0.6},
            "close_date": None,
            "resolution_date": None,
            "resolved_outcome": "",
        }
        market, created = import_market_from_normalized(data)
        self.assertTrue(created)
        self.assertEqual(market.title_es, "ES:Will inflation fall?")
        self.assertEqual(market.description_es, "ES:Resolves Yes if CPI drops below 2%.")

    @patch("markets.translation_services.translate_market_copy", side_effect=lambda text: f"ES:{text}")
    def test_import_skips_retranslation_when_copy_unchanged(self, mock_translate):
        market = Market.objects.create(
            external_id="translate-2",
            title="Stable title",
            title_es="Título estable",
            description="Stable body",
            description_es="Cuerpo estable",
            slug="stable-title",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
        )
        data = {
            "external_id": market.external_id,
            "title": market.title,
            "description": market.description,
            "category": "",
            "source": "polymarket",
            "status": "open",
            "outcomes": [],
            "current_probability": {},
            "close_date": None,
            "resolution_date": None,
            "resolved_outcome": "",
        }
        import_market_from_normalized(data)
        mock_translate.assert_not_called()

    @patch("markets.translation_services.translate_market_copy", return_value="Nuevo título")
    def test_import_retranslates_when_english_title_changes(self, mock_translate):
        market = Market.objects.create(
            external_id="translate-3",
            title="Old title",
            title_es="Título viejo",
            description="",
            slug="old-title",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
        )
        defaults = {"title": "New title", "description": ""}
        apply_spanish_translations_to_defaults(defaults, existing_market=market)
        self.assertEqual(defaults["title_es"], "Nuevo título")
        mock_translate.assert_called_once_with("New title")


class MarketDisplayCopyTests(TestCase):
    def test_display_title_uses_spanish_in_es_locale(self):
        market = Market.objects.create(
            external_id="display-1",
            title="English title",
            title_es="Título en español",
            slug="english-title",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
        )
        with translation.override("es"):
            self.assertEqual(market.display_title, "Título en español")
            self.assertEqual(market.display_description, "")

    def test_display_description_uses_spanish_in_es_locale(self):
        market = Market.objects.create(
            external_id="display-2",
            title="English title",
            description="English description",
            description_es="Descripción en español",
            slug="english-title-2",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
        )
        with translation.override("es"):
            self.assertEqual(market.display_description, "Descripción en español")
        with translation.override("en"):
            self.assertEqual(market.display_description, "English description")
