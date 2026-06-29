"""Contest earnings balance and off-platform Binance withdrawal requests."""

from __future__ import annotations

import logging
import re
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext as _

from reputation.models import ContestPayoutRequest, WeeklyContestWinner

logger = logging.getLogger(__name__)

_BINANCE_ID_RE = re.compile(r"^[0-9]{6,20}$")

ALLOWED_RECEIPT_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "application/pdf",
}
MAX_RECEIPT_BYTES = 10 * 1024 * 1024


class PayoutRequestError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class PayoutAdminError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def contest_payouts_enabled() -> bool:
    return bool(getattr(settings, "CONTEST_PAYOUTS_ENABLED", True))


def minimum_payout_usd() -> Decimal:
    return Decimal(str(getattr(settings, "CONTEST_PAYOUT_MIN_USD", 5)))


def contest_payout_notify_email() -> str:
    return str(getattr(settings, "CONTEST_PAYOUT_NOTIFY_EMAIL", "juaninappa@gmail.com")).strip()


def normalize_binance_id(binance_id: str) -> str:
    normalized = (binance_id or "").strip()
    if not _BINANCE_ID_RE.match(normalized):
        raise ValueError("invalid binance id")
    return normalized


def clean_payment_receipt(receipt):
    """Validate an optional admin-uploaded payment receipt."""
    if not receipt:
        return None

    if receipt.size > MAX_RECEIPT_BYTES:
        raise PayoutAdminError(_("Receipt must be 10 MB or smaller."))

    content_type = getattr(receipt, "content_type", "")
    if content_type and content_type not in ALLOWED_RECEIPT_CONTENT_TYPES:
        raise PayoutAdminError(_("Upload a JPEG, PNG, WebP, or PDF receipt."))

    if content_type.startswith("image/"):
        from django.core.exceptions import ValidationError

        from accounts.media_validation import clean_uploaded_image

        try:
            return clean_uploaded_image(receipt)
        except ValidationError as exc:
            raise PayoutAdminError(exc.messages[0]) from exc

    return receipt


def send_contest_payout_admin_notification(*, payout_request: ContestPayoutRequest) -> bool:
    """Notify the operator that a player submitted a withdrawal request."""
    recipient = contest_payout_notify_email()
    if not recipient:
        return False

    from accounts.email_services import EmailDeliveryError, _send

    player = payout_request.user
    context = {
        "player": player,
        "payout_request": payout_request,
    }
    try:
        _send(
            subject=lambda: _("New contest withdrawal request — %(username)s") % {
                "username": player.username
            },
            recipient_email=recipient,
            template_base="contest_payout_admin",
            context=context,
        )
    except EmailDeliveryError:
        logger.exception(
            "Contest payout admin notification failed for request_id=%s",
            payout_request.pk,
        )
        return False
    return True


def get_contest_earnings_summary(user) -> dict[str, Decimal]:
    earned_raw = (
        WeeklyContestWinner.objects.filter(user=user).aggregate(total=Sum("prize_usd"))["total"]
        or 0
    )
    earned = Decimal(str(earned_raw))

    pending_raw = (
        ContestPayoutRequest.objects.filter(
            user=user,
            status=ContestPayoutRequest.Status.PENDING,
        ).aggregate(total=Sum("amount_usd"))["total"]
        or 0
    )
    pending = Decimal(str(pending_raw))

    withdrawn_raw = (
        ContestPayoutRequest.objects.filter(
            user=user,
            status=ContestPayoutRequest.Status.PAID,
        ).aggregate(total=Sum("amount_usd"))["total"]
        or 0
    )
    withdrawn = Decimal(str(withdrawn_raw))

    available = earned - pending - withdrawn
    if available < 0:
        available = Decimal("0")

    return {
        "earned_usd": earned,
        "pending_usd": pending,
        "withdrawn_usd": withdrawn,
        "available_usd": available,
    }


def get_user_contest_wins(user):
    return WeeklyContestWinner.objects.filter(user=user).order_by("-week_code", "prize_type")


def get_user_payout_requests(user):
    return ContestPayoutRequest.objects.filter(user=user).order_by("-created_at")


def user_has_pending_payout_request(user) -> bool:
    return ContestPayoutRequest.objects.filter(
        user=user,
        status=ContestPayoutRequest.Status.PENDING,
    ).exists()


def get_platform_contest_liability_summary() -> dict:
    """Aggregate contest prize debt — awarded, in-flight withdrawals, and still owed."""
    awarded_raw = (
        WeeklyContestWinner.objects.aggregate(total=Sum("prize_usd"))["total"] or 0
    )
    paid_raw = (
        ContestPayoutRequest.objects.filter(status=ContestPayoutRequest.Status.PAID).aggregate(
            total=Sum("amount_usd")
        )["total"]
        or 0
    )
    pending_raw = (
        ContestPayoutRequest.objects.filter(
            status=ContestPayoutRequest.Status.PENDING
        ).aggregate(total=Sum("amount_usd"))["total"]
        or 0
    )
    awarded = Decimal(str(awarded_raw))
    paid = Decimal(str(paid_raw))
    pending = Decimal(str(pending_raw))
    outstanding = awarded - paid - pending
    if outstanding < 0:
        outstanding = Decimal("0")

    winner_users = WeeklyContestWinner.objects.values("user_id").distinct().count()
    finalized_weeks = WeeklyContestWinner.objects.values("week_code").distinct().count()

    return {
        "total_awarded_usd": awarded,
        "total_paid_usd": paid,
        "pending_withdrawal_usd": pending,
        "outstanding_usd": outstanding,
        "winner_count": WeeklyContestWinner.objects.count(),
        "winner_users": winner_users,
        "finalized_weeks": finalized_weeks,
    }


def get_admin_contest_winner_rows(*, limit=100):
    """All recorded weekly contest wins for the admin panel (newest first)."""
    from reputation.weekly_contest_services import week_date_range

    wins = list(
        WeeklyContestWinner.objects.select_related("user")
        .order_by("-week_code", "prize_type")[:limit]
    )
    summaries_by_user = {}
    rows = []
    for win in wins:
        if win.user_id not in summaries_by_user:
            summaries_by_user[win.user_id] = get_contest_earnings_summary(win.user)
        summary = summaries_by_user[win.user_id]
        since, until = week_date_range(win.week_code)
        rows.append(
            {
                "win": win,
                "week_start": since,
                "week_end": until - timedelta(seconds=1),
                "user_available_usd": summary["available_usd"],
                "user_earned_usd": summary["earned_usd"],
            }
        )
    return rows


def get_admin_contest_balance_rows():
    """Players with contest earnings — owed balance even if they never requested withdrawal."""
    user_ids = WeeklyContestWinner.objects.values_list("user_id", flat=True).distinct()
    if not user_ids:
        return []

    from django.contrib.auth import get_user_model

    User = get_user_model()
    rows = []
    for user in User.objects.filter(pk__in=user_ids).order_by("username"):
        summary = get_contest_earnings_summary(user)
        if summary["earned_usd"] <= 0:
            continue
        rows.append(
            {
                "user": user,
                "earned_usd": summary["earned_usd"],
                "available_usd": summary["available_usd"],
                "pending_usd": summary["pending_usd"],
                "withdrawn_usd": summary["withdrawn_usd"],
                "has_pending_request": user_has_pending_payout_request(user),
            }
        )
    rows.sort(key=lambda row: row["available_usd"], reverse=True)
    return rows


def create_payout_request(*, user, amount_usd, binance_id):
    if not contest_payouts_enabled():
        raise PayoutRequestError(_("Contest withdrawals are not available right now."))

    amount = Decimal(str(amount_usd))
    minimum = minimum_payout_usd()
    if amount < minimum:
        raise PayoutRequestError(
            _("Minimum withdrawal is $%(amount)s.") % {"amount": minimum.normalize()}
        )

    summary = get_contest_earnings_summary(user)
    if amount > summary["available_usd"]:
        raise PayoutRequestError(_("Amount exceeds your available balance."))

    if user_has_pending_payout_request(user):
        raise PayoutRequestError(_("You already have a pending withdrawal request."))

    try:
        normalized_id = normalize_binance_id(binance_id)
    except ValueError as exc:
        raise PayoutRequestError(
            _("Enter a valid Binance user ID (6–20 digits).")
        ) from exc

    payout_request = ContestPayoutRequest.objects.create(
        user=user,
        amount_usd=amount,
        binance_id=normalized_id,
    )
    send_contest_payout_admin_notification(payout_request=payout_request)
    return payout_request


def mark_payout_request_paid(
    payout_request: ContestPayoutRequest,
    *,
    payment_reference: str = "",
    payment_receipt=None,
    admin_note: str = "",
) -> ContestPayoutRequest:
    if payout_request.status != ContestPayoutRequest.Status.PENDING:
        raise PayoutAdminError(_("Only pending withdrawal requests can be marked paid."))

    receipt = clean_payment_receipt(payment_receipt)
    payout_request.status = ContestPayoutRequest.Status.PAID
    payout_request.paid_at = timezone.now()
    payout_request.payment_reference = (payment_reference or "").strip()[:128]
    payout_request.admin_note = (admin_note or "").strip()
    update_fields = ["status", "paid_at", "payment_reference", "admin_note", "updated_at"]
    if receipt:
        payout_request.payment_receipt = receipt
        update_fields.append("payment_receipt")
    payout_request.save(update_fields=update_fields)
    return payout_request


def reject_payout_request(
    payout_request: ContestPayoutRequest,
    *,
    admin_note: str = "",
) -> ContestPayoutRequest:
    if payout_request.status != ContestPayoutRequest.Status.PENDING:
        raise PayoutAdminError(_("Only pending withdrawal requests can be rejected."))

    payout_request.status = ContestPayoutRequest.Status.REJECTED
    payout_request.admin_note = (admin_note or "").strip()
    payout_request.save(update_fields=["status", "admin_note", "updated_at"])
    return payout_request
