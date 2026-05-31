"""User-facing MCP developer settings: mint, rotate, and revoke tokens (§17).

Raw token values are shown exactly once (right after creation/rotation) via a
one-shot session flash — they are never stored or shown again.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods, require_POST

from mcp.forms import McpTokenForm
from mcp.models import McpToken
from mcp.selectors import get_user_tokens
from mcp.tokens import create_token, rotate_token

_SESSION_KEY = "mcp_new_token"


def _pop_new_token(request):
    data = request.session.pop(_SESSION_KEY, None)
    if data:
        request.session.modified = True
    return data


@login_required
@require_http_methods(["GET", "POST"])
def developer_settings(request):
    if request.method == "POST":
        form = McpTokenForm(request.POST, user=request.user)
        if form.is_valid():
            token, raw = create_token(
                user=request.user,
                name=form.cleaned_data["name"],
                scopes=form.cleaned_data["scopes"],
            )
            request.session[_SESSION_KEY] = {"prefix": token.prefix, "raw": raw}
            messages.success(
                request,
                _("Token created. Copy it now — it won't be shown again."),
            )
            return redirect("mcp:developer_settings")
    else:
        form = McpTokenForm(user=request.user)

    return render(
        request,
        "mcp/developer_settings.html",
        {
            "form": form,
            "tokens": get_user_tokens(request.user),
            "new_token": _pop_new_token(request),
            "allowed_scopes": form.allowed_scopes,
            "is_agent": getattr(request.user, "is_agent_account", False),
            "agent_profile": getattr(request.user, "agent_profile", None),
        },
    )


@login_required
@require_POST
def revoke_token(request, token_id):
    token = get_object_or_404(McpToken, pk=token_id, user=request.user)
    if token.is_active:
        token.revoke()
        messages.success(request, _("Token revoked."))
    return redirect("mcp:developer_settings")


@login_required
@require_POST
def rotate_token_view(request, token_id):
    token = get_object_or_404(McpToken, pk=token_id, user=request.user)
    new_token, raw = rotate_token(token)
    request.session[_SESSION_KEY] = {"prefix": new_token.prefix, "raw": raw}
    messages.success(
        request,
        _("Token rotated. Copy the new value now — it won't be shown again."),
    )
    return redirect("mcp:developer_settings")
