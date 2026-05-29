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
from comments.models import Comment
from markets.models import Market
from predictions.models import Prediction
from pulse.models import Post as ForumPost

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
    User = get_user_model()
    now = timezone.now()
    day_ago = now - timedelta(hours=24)
    week_ago = now - timedelta(days=7)

    users = User.objects.all()
    total_users = users.count()
    active_users = users.filter(is_active=True).count()
    new_users_24h = users.filter(date_joined__gte=day_ago).count()
    new_users_7d = users.filter(date_joined__gte=week_ago).count()
    ai_agents = users.filter(is_ai_agent=True).count()
    pending_verifications = users.filter(
        verification_requested=True, is_verified=False
    ).count()

    markets = Market.objects.all()
    total_markets = markets.count()
    open_markets = markets.filter(status=Market.Status.OPEN).count()
    resolved_markets = markets.filter(status=Market.Status.RESOLVED).count()

    predictions = Prediction.objects.all()
    total_predictions = predictions.count()
    pending_predictions = predictions.filter(status=Prediction.Status.PENDING).count()
    resolved_predictions = predictions.filter(status=Prediction.Status.RESOLVED).count()

    total_comments = Comment.objects.count()
    total_forum_posts = ForumPost.objects.count()

    recent_users = users.order_by("-date_joined")[:10]
    recent_predictions = (
        predictions.select_related("user", "market").order_by("-created_at")[:8]
    )

    stat_cards = [
        {
            "label": "Total usuarios",
            "value": total_users,
            "hint": f"{active_users} activos",
            "icon": "users",
            "tone": "brand",
        },
        {
            "label": "Nuevos (24h)",
            "value": new_users_24h,
            "hint": f"{new_users_7d} esta semana",
            "icon": "user-plus",
            "tone": "emerald",
        },
        {
            "label": "Agentes IA",
            "value": ai_agents,
            "hint": "Usuarios no humanos",
            "icon": "bot",
            "tone": "violet",
        },
        {
            "label": "Verificaciones",
            "value": pending_verifications,
            "hint": "Pendientes de revisar",
            "icon": "badge-check",
            "tone": "amber",
            "stat_id": "admin-verification-stat",
        },
        {
            "label": "Mercados",
            "value": total_markets,
            "hint": f"{open_markets} abiertos · {resolved_markets} resueltos",
            "icon": "trending-up",
            "tone": "brand",
        },
        {
            "label": "Predicciones",
            "value": total_predictions,
            "hint": f"{pending_predictions} pendientes · {resolved_predictions} resueltas",
            "icon": "target",
            "tone": "emerald",
        },
        {
            "label": "Comentarios",
            "value": total_comments,
            "hint": "En mercados",
            "icon": "message-circle",
            "tone": "slate",
        },
        {
            "label": "Posts del foro",
            "value": total_forum_posts,
            "hint": "Publicaciones",
            "icon": "message-square",
            "tone": "slate",
        },
    ]

    context = {
        "stat_cards": stat_cards,
        "recent_users": recent_users,
        "recent_predictions": recent_predictions,
        **_verification_context(),
    }
    return render(request, "dashboard/admin_panel.html", context)


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
