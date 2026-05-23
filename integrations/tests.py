from django.test import TestCase

from integrations.services import import_market_from_normalized


class MarketImportServiceTests(TestCase):
    def test_import_creates_market(self):
        data = {
            "external_id": "import-1",
            "title": "Imported Market",
            "description": "Desc",
            "category": "Tech",
            "source": "polymarket",
            "status": "open",
            "outcomes": [{"label": "Yes"}, {"label": "No"}],
            "current_probability": {"Yes": 0.5, "No": 0.5},
            "close_date": None,
            "resolution_date": None,
            "resolved_outcome": "",
        }
        market, created = import_market_from_normalized(data)
        self.assertTrue(created)
        self.assertEqual(market.external_id, "import-1")
        self.assertTrue(market.slug)

    def test_import_updates_existing(self):
        data = {
            "external_id": "import-2",
            "title": "Original",
            "description": "",
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
        data["title"] = "Updated Title"
        market, created = import_market_from_normalized(data)
        self.assertFalse(created)
        self.assertEqual(market.title, "Updated Title")
