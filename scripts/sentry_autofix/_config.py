"""Sentry API base URL for PredictStamp (US region cloud)."""

from __future__ import annotations

import os


def sentry_api_base() -> str:
    region = (os.environ.get("SENTRY_REGION_URL") or "https://us.sentry.io").rstrip("/")
    return f"{region}/api/0"


def sentry_org() -> str:
    return os.environ.get("SENTRY_ORG", "fsc-ti")


def sentry_project() -> str:
    return os.environ.get("SENTRY_PROJECT", "predictstamp")
