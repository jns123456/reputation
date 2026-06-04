from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from conftest import create_user
from dashboard.admin_panel_selectors import get_admin_panel_stats


class AdminPanelSelectorTests(TestCase):
    def test_stats_use_bounded_query_count(self):
        create_user(username="u1")
        create_user(username="u2")
        with self.assertNumQueries(5):
            stats = get_admin_panel_stats()
        self.assertGreaterEqual(stats["users"]["total"], 2)


class AdminPanelViewTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="paneladmin",
            email="paneladmin@example.com",
            password="testpass123",
        )
        self.admin.email_verified_at = timezone.now()
        self.admin.onboarding_completed = True
        self.admin.save(
            update_fields=["email_verified_at", "onboarding_completed", "updated_at"]
        )

    def test_admin_panel_accessible_to_superuser(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard:admin_panel"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Total users")
