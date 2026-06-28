from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from conftest import create_user
from dashboard.admin_panel_selectors import get_admin_contest_payout_overview, get_admin_panel_stats
from reputation.models import ContestPayoutRequest, WeeklyContestWinner
from reputation.payout_services import (
    create_payout_request,
    get_platform_contest_liability_summary,
)
from reputation.tests_payout import DEFAULT_CHAIN, VALID_ADDRESS, _create_win


class AdminPanelSelectorTests(TestCase):
    def test_stats_use_bounded_query_count(self):
        create_user(username="u1")
        create_user(username="u2")
        with self.assertNumQueries(5):
            stats = get_admin_panel_stats()
        self.assertGreaterEqual(stats["users"]["total"], 2)

    def test_contest_liability_summary(self):
        winner = create_user("liabilitywinner")
        _create_win(winner, prize_usd=5)
        summary = get_platform_contest_liability_summary()
        self.assertEqual(summary["total_awarded_usd"], 5)
        self.assertEqual(summary["outstanding_usd"], 5)
        self.assertEqual(summary["winner_users"], 1)

    def test_contest_overview_includes_winners_without_withdrawal(self):
        winner = create_user("nowithdraw")
        _create_win(winner, prize_usd=5, week_code="2026-06-21")
        overview = get_admin_contest_payout_overview()
        self.assertEqual(overview["liability"]["outstanding_usd"], 5)
        self.assertEqual(len(overview["winner_rows"]), 1)
        self.assertEqual(overview["winner_rows"][0]["win"].user_id, winner.pk)
        self.assertEqual(len(overview["balance_rows"]), 1)
        self.assertEqual(overview["balance_rows"][0]["available_usd"], 5)


class AdminPanelViewTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="paneladmin",
            email="paneladmin@example.com",
            password="testpass123",
        )
        self.admin.email_verified_at = timezone.now()
        self.admin.onboarding_completed = True
        self.admin.save(
            update_fields=["email_verified_at", "onboarding_completed", "updated_at"]
        )

    def test_admin_panel_accessible_to_superuser(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:admin_panel"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Total users")

    def test_admin_panel_shows_pending_contest_withdrawals(self):
        winner = create_user("panelwinner")
        _create_win(winner)
        create_payout_request(
            user=winner,
            amount_usd=5,
            usdc_address=VALID_ADDRESS,
            chain=DEFAULT_CHAIN,
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:admin_panel"))
        self.assertContains(response, "Contest withdrawals")
        self.assertContains(response, winner.public_name)
        req = ContestPayoutRequest.objects.get(user=winner)
        self.assertContains(response, req.usdc_address)

    def test_admin_panel_shows_contest_liability_and_winners(self):
        winner = create_user("paneldebt")
        _create_win(winner, prize_usd=5, week_code="2026-06-21")
        WeeklyContestWinner.objects.create(
            user=winner,
            week_code="2026-06-21",
            prize_type=WeeklyContestWinner.PrizeType.RELATIVE,
            prize_usd=5,
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:admin_panel"))
        self.assertContains(response, "Weekly contest prizes")
        self.assertContains(response, "Outstanding debt")
        self.assertContains(response, "Player balances owed")
        self.assertContains(response, "Contest winners")
        self.assertContains(response, winner.email)
        self.assertContains(response, "$10")

    def test_admin_can_mark_contest_payout_paid(self):
        winner = create_user("panelpaid")
        _create_win(winner)
        req = create_payout_request(
            user=winner,
            amount_usd=5,
            usdc_address=VALID_ADDRESS,
            chain=DEFAULT_CHAIN,
        )
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("dashboard:resolve_contest_payout", args=[req.pk]),
            {"action": "mark_paid", "tx_hash": "0xdeadbeef"},
        )
        self.assertRedirects(response, reverse("dashboard:admin_panel"))
        req.refresh_from_db()
        self.assertEqual(req.status, ContestPayoutRequest.Status.PAID)
        self.assertEqual(req.tx_hash, "0xdeadbeef")
