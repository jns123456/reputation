"""Aggregated stats for the super-admin panel (single query per model)."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from comments.models import Comment
from markets.models import Market
from predictions.models import Prediction
from pulse.models import Post as ForumPost
from reputation.models import ContestPayoutRequest


def get_admin_panel_stats():
    """Return dashboard counters without N separate ``COUNT`` queries per metric."""
    User = get_user_model()
    now = timezone.now()
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)

    user_stats = User.objects.aggregate(
        total=Count("pk"),
        active=Count("pk", filter=Q(is_active=True)),
        new_24h=Count("pk", filter=Q(date_joined__gte=day_ago)),
        new_7d=Count("pk", filter=Q(date_joined__gte=week_ago)),
        ai_agents=Count("pk", filter=Q(is_ai_agent=True)),
        pending_verifications=Count(
            "pk",
            filter=Q(verification_requested=True, is_verified=False),
        ),
    )
    market_stats = Market.objects.aggregate(
        total=Count("pk"),
        open=Count("pk", filter=Q(status=Market.Status.OPEN)),
        resolved=Count("pk", filter=Q(status=Market.Status.RESOLVED)),
    )
    prediction_stats = Prediction.objects.aggregate(
        total=Count("pk"),
        pending=Count("pk", filter=Q(status=Prediction.Status.PENDING)),
        resolved=Count("pk", filter=Q(status=Prediction.Status.RESOLVED)),
    )
    engagement_stats = {
        "comments": Comment.objects.count(),
        "forum_posts": ForumPost.objects.count(),
    }

    return {
        "users": user_stats,
        "markets": market_stats,
        "predictions": prediction_stats,
        "engagement": engagement_stats,
    }


def build_admin_stat_cards(stats):
    """Build template-ready stat cards from ``get_admin_panel_stats()``."""
    users = stats["users"]
    markets = stats["markets"]
    predictions = stats["predictions"]
    engagement = stats["engagement"]
    return [
        {
            "label": _("Total users"),
            "value": users["total"],
            "hint": _("%(active)s active") % {"active": users["active"]},
            "icon": "users",
            "tone": "brand",
        },
        {
            "label": _("New (24h)"),
            "value": users["new_24h"],
            "hint": _("%(week)s this week") % {"week": users["new_7d"]},
            "icon": "user-plus",
            "tone": "emerald",
        },
        {
            "label": _("AI agents"),
            "value": users["ai_agents"],
            "hint": _("Non-human accounts"),
            "icon": "bot",
            "tone": "violet",
        },
        {
            "label": _("Verifications"),
            "value": users["pending_verifications"],
            "hint": _("Pending review"),
            "icon": "badge-check",
            "tone": "amber",
            "stat_id": "admin-verification-stat",
        },
        {
            "label": _("Markets"),
            "value": markets["total"],
            "hint": _("%(open)s open · %(resolved)s resolved")
            % {"open": markets["open"], "resolved": markets["resolved"]},
            "icon": "trending-up",
            "tone": "brand",
        },
        {
            "label": _("Predictions"),
            "value": predictions["total"],
            "hint": _("%(pending)s pending · %(resolved)s resolved")
            % {
                "pending": predictions["pending"],
                "resolved": predictions["resolved"],
            },
            "icon": "target",
            "tone": "emerald",
        },
        {
            "label": _("Comments"),
            "value": engagement["comments"],
            "hint": _("On markets"),
            "icon": "message-circle",
            "tone": "slate",
        },
        {
            "label": _("Forum posts"),
            "value": engagement["forum_posts"],
            "hint": _("Published posts"),
            "icon": "message-square",
            "tone": "slate",
        },
    ]


def get_admin_recent_activity():
    User = get_user_model()
    return {
        "recent_users": User.objects.order_by("-date_joined")[:10],
        "recent_predictions": Prediction.objects.select_related("user", "market").order_by(
            "-created_at"
        )[:8],
    }


def get_admin_contest_payout_overview():
    """Pending and recent contest withdrawal requests for the super-admin panel."""
    pending_qs = ContestPayoutRequest.objects.filter(
        status=ContestPayoutRequest.Status.PENDING
    ).select_related("user")
    stats = ContestPayoutRequest.objects.aggregate(
        pending_count=Count("pk", filter=Q(status=ContestPayoutRequest.Status.PENDING)),
        pending_usd=Sum("amount_usd", filter=Q(status=ContestPayoutRequest.Status.PENDING)),
        paid_count=Count("pk", filter=Q(status=ContestPayoutRequest.Status.PAID)),
        total_count=Count("pk"),
    )
    return {
        "pending_requests": pending_qs.order_by("-created_at")[:50],
        "recent_requests": ContestPayoutRequest.objects.select_related("user").order_by(
            "-created_at"
        )[:15],
        "pending_count": stats["pending_count"] or 0,
        "pending_usd": stats["pending_usd"] or 0,
        "paid_count": stats["paid_count"] or 0,
        "total_count": stats["total_count"] or 0,
    }
