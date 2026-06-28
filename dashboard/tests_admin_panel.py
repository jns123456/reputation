from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from conftest import create_user
from dashboard.admin_panel_selectors import get_admin_panel_stats
from reputation.models import ContestPayoutRequest
from reputation.payout_services import create_payout_request
from reputation.tests_payout import DEFAULT_CHAIN, VALID_ADDRESS, _create_win


class AdminPanelSelectorTests(TestCase):
    def test_stats_use_bounded_query_count(self):
        create_user(username="u1")
        create_user(username="u2")
        with self.assertNumQueries(5):
            stats = get_admin_panel_stats()
        self.assertGreaterEqual(stats["users"]["total"], 2)


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
