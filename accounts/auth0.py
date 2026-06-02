"""Auth0 (OIDC) integration helpers.

Auth0 login is an *additive* option next to the local username/password flow.
The OAuth client is configured lazily so the project still imports and runs when
Auth0 credentials are absent (``settings.AUTH0_ENABLED`` is ``False``).

Keeping this logic out of ``views.py`` follows the project's services convention:
views stay thin and the user-mapping rules live here where they are testable.
"""

from __future__ import annotations

from authlib.integrations.django_client import OAuth
from django.conf import settings
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import User

oauth = OAuth()

_REGISTERED = False


def get_auth0_client():
    """Return the registered Authlib Auth0 client, registering it on first use.

    Registration is deferred until the first login attempt so the app boots
    cleanly without Auth0 credentials (e.g. in CI or local dev).
    """
    global _REGISTERED
    if not settings.AUTH0_ENABLED:
        return None
    if not _REGISTERED:
        client_kwargs = {"scope": "openid profile email"}
        register_kwargs = {}
        if settings.AUTH0_AUDIENCE:
            register_kwargs["authorize_params"] = {"audience": settings.AUTH0_AUDIENCE}
        oauth.register(
            "auth0",
            client_id=settings.AUTH0_CLIENT_ID,
            client_secret=settings.AUTH0_CLIENT_SECRET,
            client_kwargs=client_kwargs,
            server_metadata_url=(
                f"https://{settings.AUTH0_DOMAIN}/.well-known/openid-configuration"
            ),
            **register_kwargs,
        )
        _REGISTERED = True
    return oauth.auth0


def _generate_unique_username(userinfo: dict, email: str) -> str:
    """Build a unique, URL-safe username from Auth0 profile data.

    The user can still refine their public identity during onboarding; this only
    needs to be a stable, unique handle.
    """
    base = (
        userinfo.get("nickname")
        or userinfo.get("preferred_username")
        or (email.split("@")[0] if email else "")
        or "user"
    )
    base = slugify(base).replace("-", "_")[:140] or "user"
    candidate = base
    suffix = 1
    while User.objects.filter(username__iexact=candidate).exists():
        tail = str(suffix)
        candidate = f"{base[: 140 - len(tail)]}{tail}"
        suffix += 1
    return candidate


def get_or_create_user_from_auth0(userinfo: dict) -> User:
    """Map an Auth0 ``userinfo`` payload to a local :class:`User`.

    Resolution order:
      1. Existing account already linked by ``auth0_sub``.
      2. Existing local account with a **verified** email (same address).
      3. A brand-new account (no usable password; onboarding still required).

    Unverified local signups with the same email are **not** linked — that would
    let an attacker pre-register ``victim@example.com`` and capture the victim's
    Auth0 login. When Auth0 reports the email as verified we trust it and stamp
    ``email_verified_at`` on new or legitimately linked accounts.
    """
    sub = (userinfo.get("sub") or "").strip()
    email = (userinfo.get("email") or "").strip().lower()
    email_verified = bool(userinfo.get("email_verified"))

    if sub:
        linked = User.objects.filter(auth0_sub=sub).first()
        if linked is not None:
            return linked

    if email:
        existing = User.objects.filter(email__iexact=email).first()
        if existing is not None and existing.email_verified_at is not None:
            update_fields = []
            if sub and existing.auth0_sub != sub:
                existing.auth0_sub = sub
                update_fields.append("auth0_sub")
            if email_verified and existing.email_verified_at is None:
                existing.email_verified_at = timezone.now()
                update_fields.append("email_verified_at")
            if update_fields:
                existing.save(update_fields=update_fields)
            return existing

    user = User(
        username=_generate_unique_username(userinfo, email),
        email=email,
        auth0_sub=sub,
    )
    user.set_unusable_password()
    if email_verified:
        user.email_verified_at = timezone.now()
    user.save()
    return user
