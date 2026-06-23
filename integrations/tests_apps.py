from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from integrations.apps import IntegrationsConfig


class EmbeddedSyncStartupTests(SimpleTestCase):
    @override_settings(ENABLE_EMBEDDED_MARKET_SYNC=True)
    @patch.dict("os.environ", {"DYNO": "web.1"}, clear=False)
    def test_web_dyno_skips_embedded_sync_by_default(self):
        self.assertFalse(IntegrationsConfig._should_start_embedded_sync())

    @override_settings(ENABLE_EMBEDDED_MARKET_SYNC=True)
    @patch.dict(
        "os.environ",
        {"DYNO": "web.1", "EMBEDDED_MARKET_SYNC_ON_WEB": "true"},
        clear=False,
    )
    @patch("integrations.apps.sys.argv", ["manage.py", "runserver"])
    def test_web_dyno_allows_embedded_sync_when_opted_in(self):
        self.assertTrue(IntegrationsConfig._should_start_embedded_sync())

    @override_settings(ENABLE_EMBEDDED_MARKET_SYNC=True)
    @patch.dict("os.environ", {"DYNO": "worker.1"}, clear=False)
    def test_worker_dyno_never_runs_embedded_sync(self):
        self.assertFalse(IntegrationsConfig._should_start_embedded_sync())

    @override_settings(ENABLE_EMBEDDED_MARKET_SYNC=False)
    @patch.dict("os.environ", {"DYNO": "web.1"}, clear=False)
    def test_respects_disabled_flag(self):
        self.assertFalse(IntegrationsConfig._should_start_embedded_sync())
