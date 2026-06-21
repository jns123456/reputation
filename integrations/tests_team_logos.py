"""Tests for Polymarket team logo resolution."""

from unittest.mock import MagicMock

from django.test import SimpleTestCase

from integrations.polymarket.team_logos import (
    TeamLogoResolver,
    apply_team_logos_to_soccer_match,
    infer_team_league_from_event,
    is_usable_team_logo,
    prepare_soccer_match_import,
)
from integrations.tests_soccer_matches import MEXICO_VS_RSA_EVENT


class TeamLogoHelperTests(SimpleTestCase):
    def test_is_usable_team_logo_rejects_generic_soccer_ball(self):
        self.assertFalse(
            is_usable_team_logo(
                "https://polymarket-upload.s3.us-east-2.amazonaws.com/soccer ball-bba4025f77.png"
            )
        )
        self.assertTrue(
            is_usable_team_logo(
                "https://polymarket-upload.s3.us-east-2.amazonaws.com/Belgium-3d1c700460.png"
            )
        )

    def test_infer_team_league_from_event_fifwc_slug(self):
        event = {"slug": "fifwc-bel-irn-2026-06-21", "tags": [{"slug": "fifa-world-cup"}]}
        self.assertEqual(infer_team_league_from_event(event), "fifwc")

    def test_infer_team_league_from_event_friendlies(self):
        event = {"slug": "friendly-col-cri", "tags": [{"slug": "fifa-friendlies"}]}
        self.assertEqual(infer_team_league_from_event(event), "fif")


class TeamLogoResolverTests(SimpleTestCase):
    def test_resolve_prefers_league_specific_logo(self):
        client = MagicMock()
        client.fetch_teams_by_name.side_effect = [
            [
                {
                    "name": "Belgium",
                    "league": "fifwc",
                    "logo": "https://polymarket-upload.s3.us-east-2.amazonaws.com/Belgium-3d1c700460.png",
                }
            ],
        ]
        resolver = TeamLogoResolver(client)
        logo = resolver.resolve("Belgium", league="fifwc")
        self.assertEqual(
            logo,
            "https://polymarket-upload.s3.us-east-2.amazonaws.com/Belgium-3d1c700460.png",
        )
        client.fetch_teams_by_name.assert_called_once_with("Belgium", league="fifwc")

    def test_resolve_falls_back_without_league(self):
        client = MagicMock()
        client.fetch_teams_by_name.side_effect = [
            [],
            [
                {
                    "name": "Mexico",
                    "league": "fif",
                    "logo": "https://polymarket-upload.s3.us-east-2.amazonaws.com/country-flags/mex.png",
                }
            ],
        ]
        resolver = TeamLogoResolver(client)
        logo = resolver.resolve("Mexico", league="fifwc")
        self.assertEqual(
            logo,
            "https://polymarket-upload.s3.us-east-2.amazonaws.com/country-flags/mex.png",
        )
        self.assertEqual(client.fetch_teams_by_name.call_count, 2)


class ApplyTeamLogosTests(SimpleTestCase):
    def test_apply_team_logos_enriches_outcomes_and_raw(self):
        from integrations.polymarket.soccer_matches import (
            build_world_cup_match_raw,
            normalize_world_cup_match_event,
        )

        normalized = normalize_world_cup_match_event(MEXICO_VS_RSA_EVENT)
        raw_market = build_world_cup_match_raw(MEXICO_VS_RSA_EVENT, normalized=normalized)
        client = MagicMock()
        client.fetch_teams_by_name.side_effect = [
            [{"name": "Mexico", "league": "fifwc", "logo": "https://example.com/mex.png"}],
            [{"name": "South Africa", "league": "fifwc", "logo": "https://example.com/rsa.png"}],
        ]
        apply_team_logos_to_soccer_match(
            MEXICO_VS_RSA_EVENT,
            normalized,
            raw_market,
            TeamLogoResolver(client),
        )
        self.assertEqual(raw_market["team_a_icon"], "https://example.com/mex.png")
        self.assertEqual(raw_market["team_b_icon"], "https://example.com/rsa.png")
        self.assertEqual(
            normalized["outcomes"],
            [
                {"label": "Mexico", "icon": "https://example.com/mex.png"},
                {"label": "Draw"},
                {"label": "South Africa", "icon": "https://example.com/rsa.png"},
            ],
        )


class PrepareSoccerMatchImportTests(SimpleTestCase):
    def test_prepare_soccer_match_import_with_client(self):
        client = MagicMock()
        client.fetch_teams_by_name.side_effect = [
            [{"name": "Mexico", "league": "fifwc", "logo": "https://example.com/mex.png"}],
            [{"name": "South Africa", "league": "fifwc", "logo": "https://example.com/rsa.png"}],
        ]
        normalized, raw_market = prepare_soccer_match_import(
            MEXICO_VS_RSA_EVENT,
            client=client,
        )
        self.assertIsNotNone(normalized)
        self.assertEqual(raw_market["team_a_icon"], "https://example.com/mex.png")
        self.assertEqual(normalized["outcomes"][0]["icon"], "https://example.com/mex.png")
