"""Pluggable human-verification provider abstraction (AGENTS.md §16).

Anti-bot verification (Cloudflare Turnstile, hCaptcha, etc.) is intentionally
decoupled from business logic so the provider can be swapped via settings without
touching registration or risk code. **Never rely on CAPTCHA alone** — this is one
signal among several feeding the risk score (``accounts.risk_services``).

Configure with ``HUMAN_VERIFICATION_PROVIDER`` (default ``"noop"``).
"""

from dataclasses import dataclass, field

from django.conf import settings


@dataclass
class HumanVerificationResult:
    passed: bool
    provider: str
    score: float = 0.0
    detail: dict = field(default_factory=dict)


class BaseHumanVerificationProvider:
    name = "base"

    def verify(self, *, token, request=None) -> HumanVerificationResult:  # pragma: no cover
        raise NotImplementedError


class NoopHumanVerificationProvider(BaseHumanVerificationProvider):
    """Default provider for dev/test — treats any non-empty token as passing.

    Returns ``passed=True`` even with no token so local signup is frictionless;
    production should configure a real provider. Risk scoring still applies.
    """

    name = "noop"

    def verify(self, *, token, request=None) -> HumanVerificationResult:
        return HumanVerificationResult(
            passed=True,
            provider=self.name,
            score=1.0,
            detail={"reason": "noop provider — verification not enforced"},
        )


class TurnstileHumanVerificationProvider(BaseHumanVerificationProvider):
    """Cloudflare Turnstile provider.

    Verifies a client token against the siteverify endpoint. Network/config
    failures fail *open* (passed=True, score=0.0) so an outage never locks
    legitimate users out — the missing signal simply raises risk elsewhere.
    """

    name = "turnstile"
    VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

    def verify(self, *, token, request=None) -> HumanVerificationResult:
        secret = getattr(settings, "TURNSTILE_SECRET_KEY", "")
        if not secret or not token:
            return HumanVerificationResult(
                passed=not getattr(settings, "HUMAN_VERIFICATION_REQUIRED", False),
                provider=self.name,
                score=0.0,
                detail={"reason": "missing secret or token"},
            )
        try:
            import requests

            from accounts.country_language import get_client_ip

            payload = {"secret": secret, "response": token}
            if request is not None:
                remote_ip = get_client_ip(request)
                if remote_ip:
                    payload["remoteip"] = remote_ip
            resp = requests.post(
                self.VERIFY_URL,
                data=payload,
                timeout=5,
            )
            data = resp.json()
        except Exception as exc:  # noqa: BLE001 - fail open on provider error
            return HumanVerificationResult(
                passed=True,
                provider=self.name,
                score=0.0,
                detail={"error": str(exc)},
            )
        success = bool(data.get("success"))
        return HumanVerificationResult(
            passed=success,
            provider=self.name,
            score=1.0 if success else 0.0,
            detail={"error_codes": data.get("error-codes", [])},
        )


_PROVIDERS = {
    NoopHumanVerificationProvider.name: NoopHumanVerificationProvider,
    TurnstileHumanVerificationProvider.name: TurnstileHumanVerificationProvider,
}


def get_provider() -> BaseHumanVerificationProvider:
    name = getattr(settings, "HUMAN_VERIFICATION_PROVIDER", "noop")
    provider_cls = _PROVIDERS.get(name, NoopHumanVerificationProvider)
    return provider_cls()


def verify_human_signal(*, token="", request=None) -> HumanVerificationResult:
    """Run the configured provider and return a structured result."""
    return get_provider().verify(token=token, request=request)
