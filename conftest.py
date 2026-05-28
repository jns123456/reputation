"""Test utilities and shared fixtures."""

from django.utils import timezone

from accounts.models import User, UserProfile
from markets.models import Market


def create_user(username="testuser", **kwargs):
    email = kwargs.pop("email", f"{username}@example.com")
    if email and "email_verified_at" not in kwargs:
        kwargs.setdefault("email_verified_at", timezone.now())
    user = User.objects.create_user(
        username=username,
        email=email,
        password="testpass123",
        **kwargs,
    )
    return user


def create_market(**kwargs):
    defaults = {
        "external_id": "test-market-1",
        "title": "Will it rain tomorrow?",
        "description": "Test market",
        "slug": "will-it-rain-tomorrow",
        "status": Market.Status.OPEN,
        "outcomes": [{"label": "Yes"}, {"label": "No"}],
        "current_probability": {"Yes": 0.3, "No": 0.7},
    }
    defaults.update(kwargs)
    return Market.objects.create(**defaults)
