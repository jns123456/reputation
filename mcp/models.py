"""MCP authentication tokens and audit log (AGENTS.md §17).

Tokens are hashed at rest (raw value shown once at creation). Every tool call —
allowed, denied, or dry-run — is recorded in ``McpToolCallLog`` for traceability.
Neither model ever stores raw secrets or excess private data.
"""

from django.conf import settings
from django.db import models


class McpToken(models.Model):
    """A scoped, hashed credential used to authenticate MCP requests."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="mcp_tokens",
    )
    name = models.CharField(
        max_length=120,
        help_text="Human label for the token (e.g. 'forecasting-bot-prod').",
    )
    prefix = models.CharField(
        max_length=16,
        db_index=True,
        help_text="Non-secret identifier shown in UI/logs.",
    )
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    scopes = models.JSONField(default=list, blank=True)
    rate_limit_tier = models.CharField(max_length=20, default="new")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"MCP token {self.prefix}… ({self.user_id})"

    @property
    def is_valid(self):
        from django.utils import timezone

        if not self.is_active or self.revoked_at is not None:
            return False
        if self.expires_at is not None and timezone.now() >= self.expires_at:
            return False
        return True

    def revoke(self):
        from django.utils import timezone

        self.is_active = False
        self.revoked_at = timezone.now()
        self.save(update_fields=["is_active", "revoked_at"])


class McpToolCallLog(models.Model):
    """Immutable audit record for one MCP tool/resource call."""

    class Status(models.TextChoices):
        OK = "ok", "OK"
        DRY_RUN = "dry_run", "Dry run"
        DENIED = "denied", "Denied"
        ERROR = "error", "Error"
        RATE_LIMITED = "rate_limited", "Rate limited"

    token = models.ForeignKey(
        McpToken,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="call_logs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mcp_call_logs",
    )
    agent_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="User id when the caller is an agent account (else null).",
    )
    tool_name = models.CharField(max_length=120, db_index=True)
    input_hash = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, db_index=True)
    error_code = models.CharField(max_length=80, blank=True)
    risk_score = models.PositiveIntegerField(default=0)
    request_id = models.CharField(max_length=64, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tool_name", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.tool_name} [{self.status}] @ {self.created_at:%Y-%m-%d %H:%M}"
