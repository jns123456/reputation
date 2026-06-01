from django.test import TestCase
from django.urls import reverse

from integrations.polymarket.constants import MULTI_OUTCOME_EVENT_KIND
from integrations.polymarket.soccer_matches import WORLD_CUP_MATCH_EXTERNAL_PREFIX
from markets.composite_redirect import (
    get_composite_redirect_market,
    is_orphan_polymarket_leg,
)
from markets.models import Market


class CompositeRedirectTests(TestCase):
    def setUp(self):
        self.composite = Market.objects.create(
            external_id=f"{WORLD_CUP_MATCH_EXTERNAL_PREFIX}fif-col-cri-2026-06-01",
            title="Colombia vs Costa Rica",
            slug="colombia-vs-costa-rica",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            outcomes=[
                {"label": "Colombia"},
                {"label": "Draw"},
                {"label": "Costa Rica"},
            ],
            current_probability={"Colombia": 0.86, "Draw": 0.11, "Costa Rica": 0.05},
            polymarket_raw={"market_kind": "soccer_match_3way", "event_slug": "fif-col-cri-2026-06-01"},
        )

    def test_orphan_soccer_moneyline_leg_redirects_to_composite(self):
        orphan = Market(
            external_id="123456",
            title="Will Colombia win on 2026-06-01?",
            slug="will-colombia-win-on-2026-06-01",
            source=Market.Source.POLYMARKET,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            current_probability={"Yes": 0.86, "No": 0.14},
            polymarket_raw={
                "sportsMarketType": "moneyline",
                "question": "Will Colombia win on 2026-06-01?",
            },
            polymarket_event_raw={
                "slug": "fif-col-cri-2026-06-01",
                "title": "Colombia vs Costa Rica",
            },
        )
        self.assertTrue(is_orphan_polymarket_leg(orphan))
        target = get_composite_redirect_market(orphan)
        self.assertIsNotNone(target)
        self.assertEqual(target.slug, "colombia-vs-costa-rica")

    def test_standalone_binary_is_not_orphan(self):
        standalone = Market(
            external_id="999",
            title="Will X happen?",
            slug="will-x-happen",
            source=Market.Source.POLYMARKET,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            polymarket_raw={"question": "Will X happen?"},
        )
        self.assertFalse(is_orphan_polymarket_leg(standalone))
        self.assertIsNone(get_composite_redirect_market(standalone))

    def test_composite_market_does_not_redirect(self):
        self.assertFalse(is_orphan_polymarket_leg(self.composite))
        self.assertIsNone(get_composite_redirect_market(self.composite))

    def test_grouped_submarket_leg_redirects_to_pm_event(self):
        composite = Market.objects.create(
            external_id="pm-event:dem-nominee-2028",
            title="Democratic Presidential Nominee 2028",
            slug="dem-nominee-2028",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            outcomes=[{"label": "Alice"}, {"label": "Bob"}],
            current_probability={"Alice": 0.4, "Bob": 0.35},
            polymarket_raw={"market_kind": MULTI_OUTCOME_EVENT_KIND},
        )
        orphan = Market(
            external_id="leg-alice",
            title="Will Alice win?",
            slug="will-alice-win",
            source=Market.Source.POLYMARKET,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            polymarket_raw={"groupItemTitle": "Alice"},
            polymarket_event_raw={
                "slug": "dem-nominee-2028",
                "title": composite.title,
                "markets": [
                    {"groupItemTitle": "Alice", "outcomes": '["Yes", "No"]', "closed": False},
                    {"groupItemTitle": "Bob", "outcomes": '["Yes", "No"]', "closed": False},
                ],
            },
        )
        target = get_composite_redirect_market(orphan)
        self.assertEqual(target.pk, composite.pk)


class CompositeRedirectViewTests(TestCase):
    def test_market_detail_redirects_orphan_to_composite(self):
        composite = Market.objects.create(
            external_id=f"{WORLD_CUP_MATCH_EXTERNAL_PREFIX}fif-col-cri-2026-06-01",
            title="Colombia vs Costa Rica",
            slug="colombia-vs-costa-rica",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            outcomes=[{"label": "Colombia"}, {"label": "Draw"}, {"label": "Costa Rica"}],
            polymarket_raw={"market_kind": "soccer_match_3way"},
        )
        Market.objects.create(
            external_id="orphan-col-win",
            title="Will Colombia win on 2026-06-01?",
            slug="will-colombia-win-on-2026-06-01",
            source=Market.Source.POLYMARKET,
            status=Market.Status.OPEN,
            outcomes=[{"label": "Yes"}, {"label": "No"}],
            polymarket_raw={"sportsMarketType": "moneyline"},
            polymarket_event_raw={
                "slug": "fif-col-cri-2026-06-01",
                "title": "Colombia vs Costa Rica",
                "markets": [
                    {"sportsMarketType": "moneyline", "question": "Will Colombia win?", "outcomes": '["Yes", "No"]', "closed": False},
                    {"sportsMarketType": "moneyline", "question": "Draw?", "outcomes": '["Yes", "No"]', "closed": False},
                    {"sportsMarketType": "moneyline", "question": "Will Costa Rica win?", "outcomes": '["Yes", "No"]', "closed": False},
                ],
            },
        )

        response = self.client.get(
            reverse("markets:detail", kwargs={"slug": "will-colombia-win-on-2026-06-01"}),
            follow=False,
        )
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], reverse("markets:detail", kwargs={"slug": composite.slug}))
