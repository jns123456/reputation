from django.test import TestCase

from integrations.kalshi.images import resolve_kalshi_market_image
from markets.models import Market


class KalshiImageResolutionTests(TestCase):
    def test_uses_market_specific_image_from_metadata(self):
        market = Market(
            external_id="KXNBAGAME-26MAY23NYKCLE-NYK",
            title="Game 3 winner",
            slug="game-3-winner",
            source=Market.Source.KALSHI,
            kalshi_ticker="KXNBAGAME-26MAY23NYKCLE-NYK",
            kalshi_event_raw={
                "metadata": {
                    "image_url": "https://example.com/event.webp",
                    "featured_image_url": "https://example.com/featured.webp",
                    "market_details": [
                        {
                            "market_ticker": "KXNBAGAME-26MAY23NYKCLE-NYK",
                            "image_url": "https://example.com/nyk.webp",
                        },
                        {
                            "market_ticker": "KXNBAGAME-26MAY23NYKCLE-CLE",
                            "image_url": "https://example.com/cle.webp",
                        },
                    ],
                }
            },
        )
        self.assertEqual(
            resolve_kalshi_market_image(market),
            "https://example.com/nyk.webp",
        )
        self.assertEqual(market.image_url, "https://example.com/nyk.webp")

    def test_falls_back_to_featured_image(self):
        market = Market(
            external_id="KXTEST-1",
            title="Test",
            slug="test",
            source=Market.Source.KALSHI,
            kalshi_ticker="KXTEST-1",
            kalshi_event_raw={
                "metadata": {
                    "featured_image_url": "https://example.com/featured.webp",
                    "market_details": [],
                }
            },
        )
        self.assertEqual(
            resolve_kalshi_market_image(market),
            "https://example.com/featured.webp",
        )

    def test_skips_generic_market_icon_for_series_image(self):
        market = Market(
            external_id="KXPAYROLLS-26MAY-T150000",
            title="Jobs added in May 2026",
            slug="jobs-may",
            source=Market.Source.KALSHI,
            kalshi_ticker="KXPAYROLLS-26MAY-T150000",
            kalshi_event_raw={
                "metadata": {
                    "image_url": "https://kalshi-public-docs.s3.amazonaws.com/series-images-webp/KXPAYROLLS.webp",
                    "featured_image_url": "https://kalshi-fallback-images.s3.amazonaws.com/structured_icons/hashtag.webp",
                    "market_details": [
                        {
                            "market_ticker": "KXPAYROLLS-26MAY-T150000",
                            "image_url": "https://kalshi-fallback-images.s3.amazonaws.com/structured_icons/hashtag.webp",
                        },
                    ],
                }
            },
        )
        self.assertEqual(
            resolve_kalshi_market_image(market),
            "https://kalshi-public-docs.s3.amazonaws.com/series-images-webp/KXPAYROLLS.webp",
        )
