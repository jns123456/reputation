from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

from accounts.models import SubscriberAudience


class Prediction(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", _("Pending")
        RESOLVED = "resolved", _("Resolved")
        EXITED = "exited", _("Exited")
        VOID = "void", _("Void")

    class Direction(models.TextChoices):
        YES = "yes", _("Yes")
        NO = "no", _("No")

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="predictions",
    )
    market = models.ForeignKey(
        "markets.Market",
        on_delete=models.CASCADE,
        related_name="predictions",
    )
    predicted_outcome = models.CharField(max_length=255)
    predicted_direction = models.CharField(
        max_length=10,
        choices=Direction.choices,
        default=Direction.YES,
    )
    confidence = models.FloatField(default=0.5)
    probability_at_prediction_time = models.JSONField(default=dict, blank=True)
    reasoning = models.TextField(blank=True)
    audience = models.CharField(
        max_length=20,
        choices=SubscriberAudience.choices,
        default=SubscriberAudience.PUBLIC,
        db_index=True,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    is_correct = models.BooleanField(null=True, blank=True)
    popularity_score = models.IntegerField(default=0)
    superseded_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="supersedes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    probability_at_exit_time = models.JSONField(default=dict, blank=True)
    exited_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["market", "status"]),
            models.Index(fields=["user", "status"]),
            # Backs the Forecasts feed: status filter + newest-first ordering.
            models.Index(fields=["status", "-created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "market"],
                condition=Q(status="pending"),
                name="unique_pending_prediction_per_user_market",
            ),
        ]

    def __str__(self):
        direction = self.get_predicted_direction_display()
        return f"{self.user.username} → {direction} {self.predicted_outcome} on {self.market.title}"

    @property
    def is_resolved(self):
        return self.status == self.Status.RESOLVED

    @property
    def is_editable(self):
        return False

    @property
    def verified_attestation(self):
        """Return the subtle proof receipt shown in forecast UI when available."""
        prefetched = getattr(self, "_prefetched_objects_cache", {}).get("attestations")
        if prefetched is not None:
            for attestation in prefetched:
                if (
                    attestation.status == "verified"
                    and attestation.schema.kind == "prediction_claim"
                ):
                    return attestation
            return None

        return (
            self.attestations.filter(
                schema__kind="prediction_claim",
                status="verified",
            )
            .select_related("schema")
            .order_by("-created_at")
            .first()
        )
