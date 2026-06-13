"""Tests for Sentry autofix denylist."""

import sys
from pathlib import Path

from django.test import SimpleTestCase

_DENYLIST_DIR = Path(__file__).resolve().parents[1] / "scripts" / "sentry_autofix"
sys.path.insert(0, str(_DENYLIST_DIR))
from _denylist import forbidden_files, load_patterns, path_matches  # noqa: E402


class AutofixDenylistTests(SimpleTestCase):
    def test_reputation_services_blocked(self):
        patterns = load_patterns()
        self.assertIn(
            "reputation/services.py",
            forbidden_files(["reputation/services.py"], patterns),
        )

    def test_views_allowed(self):
        patterns = load_patterns()
        self.assertEqual(
            forbidden_files(["dashboard/views.py"], patterns),
            [],
        )

    def test_migration_glob(self):
        patterns = load_patterns()
        self.assertTrue(path_matches(patterns, "accounts/migrations/0001_initial.py"))
