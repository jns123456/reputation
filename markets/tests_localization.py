from django.test import TestCase
from django.utils import translation

from markets.localization import localize_category_label, localize_outcome_label


class MarketLocalizationTests(TestCase):
    def test_category_spanish_mapping(self):
        with translation.override("es"):
            self.assertEqual(localize_category_label("Politics"), "Política")
            self.assertEqual(localize_category_label("Sports"), "Deportes")

    def test_outcome_spanish_yes_no(self):
        with translation.override("es"):
            self.assertEqual(localize_outcome_label("Yes"), "Sí")
            self.assertEqual(localize_outcome_label("No"), "No")

    def test_proper_noun_outcome_unchanged(self):
        with translation.override("es"):
            self.assertEqual(localize_outcome_label("Donald Trump"), "Donald Trump")
