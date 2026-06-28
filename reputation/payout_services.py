"""Contest earnings balance and off-platform USDT withdrawal requests."""

from __future__ import annotations

import logging
import re
from decimal import Decimal

from django.conf import settings
from django.db.models import Sum
from django.utils.translation import gettext as _

from reputation.models import ContestPayoutRequest, WeeklyContestWinner

logger = logging.getLogger(__name__)

_USDT_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


class PayoutRequestError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def contest_payouts_enabled() -> bool:
    return bool(getattr(settings, "CONTEST_PAYOUTS_ENABLED", True))


def minimum_payout_usd() -> Decimal:
    return Decimal(str(getattr(settings, "CONTEST_PAYOUT_MIN_USD", 5)))


def normalize_usdc_address(address: str) -> str:
    normalized = (address or "").strip()
    if not _USDT_ADDRESS_RE.match(normalized):
        raise ValueError("invalid address")
    return normalized


def contest_payout_notify_email() -> str:
    return str(getattr(settings, "CONTEST_PAYOUT_NOTIFY_EMAIL", "juaninappa@gmail.com")).strip()


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


def create_payout_request(*, user, amount_usd, usdc_address):
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
        normalized_address = normalize_usdc_address(usdc_address)
    except ValueError as exc:
        raise PayoutRequestError(
            _("Enter a valid USDT wallet address (0x…).")
        ) from exc

    payout_request = ContestPayoutRequest.objects.create(
        user=user,
        amount_usd=amount,
        usdc_address=normalized_address,
        chain=ContestPayoutRequest.Chain.BASE,
    )
    send_contest_payout_admin_notification(payout_request=payout_request)
    return payout_request
