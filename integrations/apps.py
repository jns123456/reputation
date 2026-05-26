import os
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
        if "runserver" in sys.argv:
            return True
        dyno = os.environ.get("DYNO", "")
        return dyno.startswith("web.")
