"""Test utilities and shared fixtures."""

from accounts.models import User, UserProfile
from markets.models import Market


def create_user(username="testuser", **kwargs):
    user = User.objects.create_user(
        username=username,
        email=f"{username}@example.com",
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
