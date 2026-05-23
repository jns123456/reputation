from django.conf import settings
from django.db import models


class Prediction(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RESOLVED = "resolved", "Resolved"
        VOID = "void", "Void"

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
    confidence = models.FloatField(default=0.5)
    probability_at_prediction_time = models.JSONField(default=dict, blank=True)
    reasoning = models.TextField(blank=True)
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

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["market", "status"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return f"{self.user.username} → {self.predicted_outcome} on {self.market.title}"

    @property
    def is_resolved(self):
        return self.status == self.Status.RESOLVED

    @property
    def is_editable(self):
        return False
