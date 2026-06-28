"""Platform super-admin control panel.

Operational overview restricted to super admins (``is_superuser``). Identity
verification requests can be approved or rejected here; deeper management still
lives in Django Admin (``/admin/``).
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.identity_verification_services import (
    IdentityVerificationError,
    approve_identity_verification,
    get_pending_verification_users,
    reject_identity_verification,
)
from accounts.models import AbuseEvent, AIAgentProfile
from dashboard.admin_panel_selectors import (
    build_admin_stat_cards,
    get_admin_contest_payout_overview,
    get_admin_panel_stats,
    get_admin_recent_activity,
)

superadmin_required = user_passes_test(lambda u: u.is_active and u.is_superuser)


def _verification_context():
    pending_users = get_pending_verification_users()
    pending_count = pending_users.count()
    return {
        "pending_verification_users": pending_users,
        "pending_verifications": pending_count,
    }


@superadmin_required
def admin_panel(request):
    stats = get_admin_panel_stats()
    recent = get_admin_recent_activity()
    context = {
        "stat_cards": build_admin_stat_cards(stats),
        "recent_users": recent["recent_users"],
        "recent_predictions": recent["recent_predictions"],
        "contest_payouts": get_admin_contest_payout_overview(),
        **_verification_context(),
    }
    return render(request, "dashboard/admin_panel.html", context)


@superadmin_required
@require_POST
def resolve_contest_payout(request, payout_id):
    from django.contrib import messages

    from reputation.models import ContestPayoutRequest
    from reputation.payout_services import PayoutRequestError, resolve_contest_payout_request

    payout = get_object_or_404(ContestPayoutRequest.objects.select_related("user"), pk=payout_id)
    action = request.POST.get("action", "")
    tx_hash = request.POST.get("tx_hash", "")

    try:
        resolve_contest_payout_request(
            payout_request=payout,
            action=action,
            tx_hash=tx_hash,
        )
    except PayoutRequestError as exc:
        messages.error(request, exc.message)
    else:
        if action == "mark_paid":
            messages.success(
                request,
                f"Marked ${payout.amount_usd} withdrawal for @{payout.user.username} as paid.",
            )
        elif action == "mark_rejected":
            messages.success(
                request,
                f"Rejected withdrawal request for @{payout.user.username}.",
            )

    return redirect("dashboard:admin_panel")


@superadmin_required
@require_POST
def resolve_identity_verification(request, user_id):
    User = get_user_model()
    user = get_object_or_404(User, pk=user_id)
    action = request.POST.get("action")

    try:
        if action == "approve":
            approve_identity_verification(user)
        elif action == "reject":
            reject_identity_verification(user)
        else:
            return HttpResponseBadRequest("Invalid action.")
    except IdentityVerificationError:
        pass

    context = _verification_context()
    if request.headers.get("HX-Request"):
        return render(
            request,
            "dashboard/partials/verification_review_response.html",
            context,
        )
    return redirect("dashboard:admin_panel")


@superadmin_required
def moderation_queue(request):
    """Anti-abuse moderation queue: recent abuse events, agents, suspicious users (§16)."""
    User = get_user_model()

    event_type = request.GET.get("event_type") or ""
    severity = request.GET.get("severity") or ""
    abuse_events = AbuseEvent.objects.select_related("user").all()
    if event_type:
        abuse_events = abuse_events.filter(event_type=event_type)
    if severity:
        abuse_events = abuse_events.filter(severity=severity)
    abuse_events = abuse_events[:100]

    week_ago = timezone.now() - timedelta(days=7)
    context = {
        "abuse_events": abuse_events,
        "event_type_filter": event_type,
        "severity_filter": severity,
        "event_types": AbuseEvent.EventType.choices,
        "severities": AbuseEvent.Severity.choices,
        "high_severity_7d": AbuseEvent.objects.filter(
            severity=AbuseEvent.Severity.HIGH, created_at__gte=week_ago
        ).count(),
        "agents": AIAgentProfile.objects.select_related("user").order_by(
            "trust_level", "-updated_at"
        )[:100],
        "suspicious_users": User.objects.filter(
            account_type=User.AccountType.SUSPICIOUS
        ).order_by("-date_joined")[:50],
        "agent_actions": ["promote", "verify", "restrict", "ban", "reset_standard"],
        "user_actions": ["clear_suspicious", "mark_suspicious"],
    }
    return render(request, "dashboard/moderation_queue.html", context)


@superadmin_required
@require_POST
def moderation_action(request):
    from accounts.moderation_services import bulk_moderate

    action = request.POST.get("action", "")
    user_ids = request.POST.getlist("user_ids")
    try:
        user_ids = [int(uid) for uid in user_ids]
    except (TypeError, ValueError):
        return HttpResponseBadRequest("Invalid user ids.")

    affected = bulk_moderate(action=action, user_ids=user_ids)
    from django.contrib import messages

    messages.success(request, f"Applied '{action}' to {affected} account(s).")
    return redirect("dashboard:moderation_queue")
