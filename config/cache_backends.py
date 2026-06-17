"""Cache backends that tolerate transient Redis outages on Heroku."""

import logging

from django.core.cache.backends.redis import RedisCache

logger = logging.getLogger(__name__)


class ResilientRedisCache(RedisCache):
    """Redis cache that never raises on connection errors.

    Cache is an optimization layer: a dropped TLS socket or exhausted connection
    pool must degrade to a cache miss (recompute from DB), not a 500 for users.
    """

    def _log_cache_error(self, operation: str, key, exc: Exception) -> None:
        logger.warning(
            "Cache %s failed for %r (%s: %s); treating as miss/no-op",
            operation,
            key,
            type(exc).__name__,
            exc,
        )

    def get(self, key, default=None, version=None):
        try:
            return super().get(key, default, version)
        except Exception as exc:
            self._log_cache_error("get", key, exc)
            return default

    def set(self, key, value, timeout=None, version=None):
        try:
            return super().set(key, value, timeout, version)
        except Exception as exc:
            self._log_cache_error("set", key, exc)
            return False

    def add(self, key, value, timeout=None, version=None):
        try:
            return super().add(key, value, timeout, version)
        except Exception as exc:
            self._log_cache_error("add", key, exc)
            return False

    def delete(self, key, version=None):
        try:
            return super().delete(key, version)
        except Exception as exc:
            self._log_cache_error("delete", key, exc)
            return False

    def get_many(self, keys, version=None):
        try:
            return super().get_many(keys, version)
        except Exception as exc:
            self._log_cache_error("get_many", keys, exc)
            return {}

    def set_many(self, data, timeout=None, version=None):
        try:
            return super().set_many(data, timeout, version)
        except Exception as exc:
            self._log_cache_error("set_many", list(data.keys()), exc)
            return []

    def delete_many(self, keys, version=None):
        try:
            return super().delete_many(keys, version)
        except Exception as exc:
            self._log_cache_error("delete_many", keys, exc)
            return False

    def has_key(self, key, version=None):
        try:
            return super().has_key(key, version)
        except Exception as exc:
            self._log_cache_error("has_key", key, exc)
            return False
