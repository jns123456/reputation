from django.conf import settings
from django.db import models


class ReputationEvent(models.Model):
    class EventType(models.TextChoices):
        CORRECT_PREDICTION = "correct_prediction", "Correct prediction"
        INCORRECT_PREDICTION = "incorrect_prediction", "Incorrect prediction"
        VOID_PREDICTION = "void_prediction", "Void prediction"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reputation_events",
    )
    prediction = models.ForeignKey(
        "predictions.Prediction",
        on_delete=models.CASCADE,
        related_name="reputation_events",
    )
    event_type = models.CharField(max_length=50, choices=EventType.choices)
    points_delta = models.IntegerField()
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event_type}: {self.points_delta} for {self.user.username}"


class PopularityEvent(models.Model):
    class EventType(models.TextChoices):
        UPVOTE_RECEIVED = "upvote_received", "Upvote received"
        DOWNVOTE_RECEIVED = "downvote_received", "Downvote received"
        COMMENT_POSTED = "comment_posted", "Comment posted"
        REPLY_RECEIVED = "reply_received", "Reply received"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="popularity_events",
    )
    comment = models.ForeignKey(
        "comments.Comment",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="popularity_events",
    )
    prediction = models.ForeignKey(
        "predictions.Prediction",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="popularity_events",
    )
    event_type = models.CharField(max_length=50, choices=EventType.choices)
    points_delta = models.IntegerField()
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.event_type}: {self.points_delta} for {self.user.username}"
