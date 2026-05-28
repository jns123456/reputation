"""HTTP endpoints for Web Push subscription management."""

import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from accounts.push_services import (
    delete_subscription,
    get_vapid_public_key,
    is_enabled,
    save_subscription,
)


@require_GET
def vapid_public_key(request):
    """Expose the VAPID public key the browser needs to subscribe."""
    return JsonResponse({"enabled": is_enabled(), "publicKey": get_vapid_public_key()})


@login_required
@require_POST
def push_subscribe(request):
    if not is_enabled():
        return JsonResponse({"ok": False, "error": "disabled"}, status=503)
    try:
        payload = json.loads(request.body or "{}")
        subscription = payload.get("subscription") or payload
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "invalid_json"}, status=400)

    try:
        save_subscription(
            user=request.user,
            subscription=subscription,
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
    except ValueError:
        return JsonResponse({"ok": False, "error": "invalid_subscription"}, status=400)
    return JsonResponse({"ok": True})


@login_required
@require_POST
def push_unsubscribe(request):
    try:
        payload = json.loads(request.body or "{}")
    except (ValueError, TypeError):
        return JsonResponse({"ok": False, "error": "invalid_json"}, status=400)

    endpoint = payload.get("endpoint")
    delete_subscription(user=request.user, endpoint=endpoint)
    return JsonResponse({"ok": True})
