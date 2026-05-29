from unittest.mock import patch

from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.test import SimpleTestCase

from config.cache_backends import ResilientRedisCache


class ResilientRedisCacheTests(SimpleTestCase):
    def setUp(self):
        self.backend = ResilientRedisCache("redis://localhost:6379/0", {})

    @patch("django.core.cache.backends.redis.RedisCache.get", side_effect=ConnectionError("redis down"))
    def test_get_returns_default_on_connection_error(self, _mock_get):
        self.assertIsNone(self.backend.get("missing-key"))
        self.assertEqual(self.backend.get("missing-key", default="fallback"), "fallback")

    @patch("django.core.cache.backends.redis.RedisCache.set", side_effect=ConnectionError("redis down"))
    def test_set_returns_false_on_connection_error(self, _mock_set):
        self.assertFalse(self.backend.set("key", "value", timeout=DEFAULT_TIMEOUT))

    @patch("django.core.cache.backends.redis.RedisCache.delete", side_effect=ConnectionError("redis down"))
    def test_delete_returns_false_on_connection_error(self, _mock_delete):
        self.assertFalse(self.backend.delete("key"))

    @patch("django.core.cache.backends.redis.RedisCache.get_many", side_effect=ConnectionError("redis down"))
    def test_get_many_returns_empty_on_connection_error(self, _mock_get_many):
        self.assertEqual(self.backend.get_many(["a", "b"]), {})
