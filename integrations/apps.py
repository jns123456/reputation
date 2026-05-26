import sys

from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "integrations"

    def ready(self):
        if self._should_start_embedded_sync():
            from integrations.market_sync_scheduler import start_embedded_market_sync_scheduler

            start_embedded_market_sync_scheduler()

    @staticmethod
    def _should_start_embedded_sync():
        if "test" in sys.argv:
            return False
        if any(cmd in sys.argv for cmd in ("migrate", "collectstatic", "shell", "createsuperuser")):
            return False
        return True
