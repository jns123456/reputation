"""Tests for CSP helper utilities."""

from django.test import SimpleTestCase

from config.csp_helpers import sentry_csp_report_uri


class SentryCspReportUriTests(SimpleTestCase):
    def test_builds_report_uri_from_dsn(self):
        uri = sentry_csp_report_uri(
            "https://abc123@o999.ingest.us.sentry.io/4511553501790208"
        )
        self.assertEqual(
            uri,
            "https://o999.ingest.us.sentry.io/api/4511553501790208/security/?sentry_key=abc123",
        )

    def test_empty_when_dsn_missing(self):
        self.assertEqual(sentry_csp_report_uri(""), "")
