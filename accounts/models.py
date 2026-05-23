from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    display_name = models.CharField(max_length=150, blank=True)
    is_anonymous_profile = models.BooleanField(
        default=False,
        help_text="Whether the user prefers an anonymous public profile.",
    )
    is_ai_agent = models.BooleanField(default=False)
    bio = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["username"]

    def __str__(self):
        return self.public_name

    @property
    def public_name(self):
        if self.is_anonymous_profile and self.display_name:
            return self.display_name
        if self.display_name:
            return self.display_name
        return self.username


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    popularity_points = models.IntegerField(default=0)
    reputation_points = models.IntegerField(default=0)
    prediction_count = models.PositiveIntegerField(default=0)
    correct_prediction_count = models.PositiveIntegerField(default=0)
    incorrect_prediction_count = models.PositiveIntegerField(default=0)
    neutral_prediction_count = models.PositiveIntegerField(default=0)
    reputation_score = models.FloatField(default=0.0)
    popularity_score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-reputation_score"]

    def __str__(self):
        return f"Profile: {self.user.username}"


class UserCategoryStats(models.Model):
    """Per-category reputation and popularity aggregates for a user."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="category_stats",
    )
    category_slug = models.CharField(max_length=50)
    reputation_points = models.IntegerField(default=0)
    popularity_points = models.IntegerField(default=0)
    prediction_count = models.PositiveIntegerField(default=0)
    correct_prediction_count = models.PositiveIntegerField(default=0)
    incorrect_prediction_count = models.PositiveIntegerField(default=0)
    reputation_score = models.FloatField(default=0.0)
    popularity_score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("user", "category_slug")]
        indexes = [
            models.Index(fields=["category_slug", "-reputation_score"]),
            models.Index(fields=["category_slug", "-popularity_score"]),
        ]
        ordering = ["category_slug"]
        verbose_name_plural = "User category stats"

    def __str__(self):
        return f"{self.user.username} · {self.category_slug}"


class AIAgentProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="agent_profile",
    )
    agent_name = models.CharField(max_length=150)
    model_provider = models.CharField(max_length=100, blank=True)
    model_name = models.CharField(max_length=100, blank=True)
    system_description = models.TextField(blank=True)
    is_verified_agent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AI agent profile"

    def __str__(self):
        return self.agent_name


class Bookmark(models.Model):
    class TargetType(models.TextChoices):
        PREDICTION = "prediction", "Prediction"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bookmarks",
    )
    target_type = models.CharField(max_length=20, choices=TargetType.choices)
    target_id = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "target_type", "target_id")]
        indexes = [
            models.Index(fields=["user", "target_type"]),
            models.Index(fields=["target_type", "target_id"]),
        ]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} bookmarked {self.target_type}:{self.target_id}"
