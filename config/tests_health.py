from django.test import TestCase, override_settings
from django.urls import reverse


class HealthEndpointTests(TestCase):
    def test_health_returns_ok_with_database(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["checks"]["database"], "ok")

    @override_settings(USE_REDIS_CACHE=False)
    def test_health_skips_cache_when_not_using_redis(self):
        response = self.client.get(reverse("health"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["checks"]["cache"], "skipped")
