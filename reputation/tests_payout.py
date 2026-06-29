"""Contest earnings balance and Binance withdrawal requests."""

from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from conftest import create_user
from reputation.models import ContestPayoutRequest, WeeklyContestWinner
from reputation.payout_services import (
    PayoutAdminError,
    PayoutRequestError,
    create_payout_request,
    get_contest_earnings_summary,
    mark_payout_request_paid,
    reject_payout_request,
)

VALID_BINANCE_ID = "123456789"


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
            binance_id=VALID_BINANCE_ID,
        )
        summary = get_contest_earnings_summary(self.user)
        self.assertEqual(summary["pending_usd"], Decimal("5"))
        self.assertEqual(summary["available_usd"], Decimal("5"))

        req.status = ContestPayoutRequest.Status.PAID
        req.save(update_fields=["status"])
        summary = get_contest_earnings_summary(self.user)
        self.assertEqual(summary["withdrawn_usd"], Decimal("5"))
        self.assertEqual(summary["available_usd"], Decimal("5"))

    def test_rejects_invalid_binance_id(self):
        _create_win(self.user)
        with self.assertRaises(PayoutRequestError):
            create_payout_request(
                user=self.user,
                amount_usd=Decimal("5"),
                binance_id="not-an-id",
            )

    def test_rejects_duplicate_pending_request(self):
        _create_win(self.user)
        create_payout_request(
            user=self.user,
            amount_usd=Decimal("5"),
            binance_id=VALID_BINANCE_ID,
        )
        with self.assertRaises(PayoutRequestError):
            create_payout_request(
                user=self.user,
                amount_usd=Decimal("5"),
                binance_id=VALID_BINANCE_ID,
            )

    def test_rejects_below_minimum(self):
        _create_win(self.user, prize_usd=5)
        with self.assertRaises(PayoutRequestError):
            create_payout_request(
                user=self.user,
                amount_usd=Decimal("4"),
                binance_id=VALID_BINANCE_ID,
            )

    def test_mark_paid_with_receipt(self):
        _create_win(self.user)
        req = create_payout_request(
            user=self.user,
            amount_usd=Decimal("5"),
            binance_id=VALID_BINANCE_ID,
        )
        receipt = SimpleUploadedFile(
            "receipt.pdf",
            b"%PDF-1.4 test",
            content_type="application/pdf",
        )
        mark_payout_request_paid(
            req,
            payment_reference="BN12345",
            payment_receipt=receipt,
        )
        req.refresh_from_db()
        self.assertEqual(req.status, ContestPayoutRequest.Status.PAID)
        self.assertEqual(req.payment_reference, "BN12345")
        self.assertTrue(req.payment_receipt)

    def test_reject_pending_request(self):
        _create_win(self.user)
        req = create_payout_request(
            user=self.user,
            amount_usd=Decimal("5"),
            binance_id=VALID_BINANCE_ID,
        )
        reject_payout_request(req, admin_note="Invalid ID")
        req.refresh_from_db()
        self.assertEqual(req.status, ContestPayoutRequest.Status.REJECTED)
        self.assertEqual(req.admin_note, "Invalid ID")

    def test_cannot_mark_non_pending_paid(self):
        _create_win(self.user)
        req = create_payout_request(
            user=self.user,
            amount_usd=Decimal("5"),
            binance_id=VALID_BINANCE_ID,
        )
        reject_payout_request(req)
        with self.assertRaises(PayoutAdminError):
            mark_payout_request_paid(req)


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
            {"amount_usd": "5", "binance_id": VALID_BINANCE_ID},
        )
        self.assertRedirects(response, self.url)
        self.assertEqual(ContestPayoutRequest.objects.filter(user=self.user).count(), 1)

    def test_spanish_renders(self):
        _create_win(self.user)
        self.client.force_login(self.user)
        response = self.client.get(self.url, HTTP_ACCEPT_LANGUAGE="es")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ganancias del concurso")


@override_settings(CONTEST_PAYOUTS_ENABLED=True, CONTEST_PAYOUT_MIN_USD=5)
class AdminContestPayoutPanelTests(TestCase):
    def setUp(self):
        self.admin = create_user("superadmin", is_superuser=True)
        self.winner = create_user("weeklywinner")
        self.client = Client()
        _create_win(self.winner)
        self.payout = create_payout_request(
            user=self.winner,
            amount_usd=Decimal("5"),
            binance_id=VALID_BINANCE_ID,
        )

    def test_admin_panel_shows_pending_payout(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:admin_panel"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, VALID_BINANCE_ID)
        self.assertContains(response, "Contest withdrawals")

    def test_mark_paid_from_admin_panel(self):
        self.client.force_login(self.admin)
        url = reverse("dashboard:resolve_contest_payout", args=[self.payout.pk])
        response = self.client.post(
            url,
            {
                "action": "mark_paid",
                "payment_reference": "BN999",
            },
        )
        self.assertRedirects(response, reverse("dashboard:admin_panel"))
        self.payout.refresh_from_db()
        self.assertEqual(self.payout.status, ContestPayoutRequest.Status.PAID)
        self.assertEqual(self.payout.payment_reference, "BN999")

    def test_non_superuser_cannot_access_panel(self):
        self.client.force_login(self.winner)
        response = self.client.get(reverse("dashboard:admin_panel"))
        self.assertEqual(response.status_code, 302)

    def test_admin_panel_spanish_renders(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:admin_panel"), HTTP_ACCEPT_LANGUAGE="es")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Retiros del concurso")
