"""Tests for CSP helper utilities."""

from django.test import SimpleTestCase

from config.csp_helpers import (
    ensure_frame_src_host,
    ensure_turnstile_frame_src,
    sentry_csp_report_uri,
)


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


class EnsureFrameSrcHostTests(SimpleTestCase):
    def test_adds_host_to_frame_src(self):
        policy = "default-src 'self'; frame-src 'self' embed.polymarket.com; connect-src 'self';"
        patched = ensure_turnstile_frame_src(policy)
        self.assertIn(
            "frame-src 'self' embed.polymarket.com challenges.cloudflare.com;",
            patched,
        )

    def test_idempotent_when_host_present(self):
        policy = (
            "default-src 'self'; "
            "frame-src 'self' challenges.cloudflare.com; "
            "connect-src 'self';"
        )
        self.assertEqual(ensure_turnstile_frame_src(policy), policy)

    def test_noop_without_frame_src(self):
        policy = "default-src 'self'; connect-src 'self';"
        self.assertEqual(ensure_frame_src_host(policy, "example.com"), policy)
