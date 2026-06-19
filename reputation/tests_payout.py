"""Contest earnings balance and USDC withdrawal requests."""

from decimal import Decimal

from django.test import Client, TestCase, override_settings
from django.urls import reverse

from conftest import create_user
from reputation.models import ContestPayoutRequest, WeeklyContestWinner
from reputation.payout_services import (
    PayoutRequestError,
    create_payout_request,
    get_contest_earnings_summary,
)

VALID_ADDRESS = "0x" + "a" * 40


def _create_win(user, *, prize_usd=5, week_code="2026-06-21"):
    return WeeklyContestWinner.objects.create(
        user=user,
        week_code=week_code,
        prize_type=WeeklyContestWinner.PrizeType.ABSOLUTE,
        prize_usd=prize_usd,
    )


@override_settings(CONTEST_PAYOUTS_ENABLED=True, CONTEST_PAYOUT_MIN_USD=5)
class ContestPayoutServicesTests(TestCase):
    def setUp(self):
        self.user = create_user("payoutuser")

    def test_balance_from_wins_minus_withdrawals(self):
        _create_win(self.user, prize_usd=5)
        _create_win(self.user, prize_usd=5, week_code="2026-06-28")
        summary = get_contest_earnings_summary(self.user)
        self.assertEqual(summary["earned_usd"], Decimal("10"))
        self.assertEqual(summary["available_usd"], Decimal("10"))

        req = create_payout_request(
            user=self.user,
            amount_usd=Decimal("5"),
            usdc_address=VALID_ADDRESS,
        )
        summary = get_contest_earnings_summary(self.user)
        self.assertEqual(summary["pending_usd"], Decimal("5"))
        self.assertEqual(summary["available_usd"], Decimal("5"))

        req.status = ContestPayoutRequest.Status.PAID
        req.save(update_fields=["status"])
        summary = get_contest_earnings_summary(self.user)
        self.assertEqual(summary["withdrawn_usd"], Decimal("5"))
        self.assertEqual(summary["available_usd"], Decimal("5"))

    def test_rejects_invalid_address(self):
        _create_win(self.user)
        with self.assertRaises(PayoutRequestError):
            create_payout_request(
                user=self.user,
                amount_usd=Decimal("5"),
                usdc_address="not-an-address",
            )

    def test_rejects_duplicate_pending_request(self):
        _create_win(self.user)
        create_payout_request(
            user=self.user,
            amount_usd=Decimal("5"),
            usdc_address=VALID_ADDRESS,
        )
        with self.assertRaises(PayoutRequestError):
            create_payout_request(
                user=self.user,
                amount_usd=Decimal("5"),
                usdc_address=VALID_ADDRESS,
            )

    def test_rejects_below_minimum(self):
        _create_win(self.user, prize_usd=5)
        with self.assertRaises(PayoutRequestError):
            create_payout_request(
                user=self.user,
                amount_usd=Decimal("4"),
                usdc_address=VALID_ADDRESS,
            )


@override_settings(CONTEST_PAYOUTS_ENABLED=True, CONTEST_PAYOUT_MIN_USD=5)
class ProfileContestEarningsViewTests(TestCase):
    def setUp(self):
        self.user = create_user("earningsview")
        self.other = create_user("otheruser")
        self.client = Client()
        self.url = reverse("accounts:profile_contest_earnings", args=[self.user.username])

    def test_requires_login(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)

    def test_owner_can_view_balance(self):
        _create_win(self.user)
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Available balance")
        self.assertContains(response, "$5")

    def test_non_owner_redirected(self):
        self.client.force_login(self.other)
        response = self.client.get(self.url)
        self.assertRedirects(response, reverse("accounts:profile", args=[self.user.username]))

    def test_submit_withdrawal_request(self):
        _create_win(self.user)
        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            {"amount_usd": "5", "usdc_address": VALID_ADDRESS},
        )
        self.assertRedirects(response, self.url)
        self.assertEqual(ContestPayoutRequest.objects.filter(user=self.user).count(), 1)

    def test_spanish_renders(self):
        _create_win(self.user)
        self.client.force_login(self.user)
        response = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE="es")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ganancias del concurso")
