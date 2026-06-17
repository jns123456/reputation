"""Tests for CSP helper utilities."""

from django.test import SimpleTestCase

from config.csp_helpers import (
    ensure_connect_src_host,
    ensure_font_src_host,
    ensure_frame_src_host,
    ensure_google_fonts_font_src,
    ensure_iconify_connect_src,
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


class BuildContentSecurityPolicyTests(SimpleTestCase):
    def test_turnstile_allowed_in_frame_src(self):
        from config.settings import build_content_security_policy

        policy = build_content_security_policy()
        frame_part = policy.split("frame-src")[1].split(";")[0]
        self.assertIn("challenges.cloudflare.com", frame_part)
        self.assertIn("embed.polymarket.com", frame_part)


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


class EnsureFontSrcHostTests(SimpleTestCase):
    def test_adds_host_to_font_src(self):
        policy = "default-src 'self'; font-src 'self' data:; connect-src 'self';"
        patched = ensure_google_fonts_font_src(policy)
        self.assertIn("font-src 'self' data: fonts.gstatic.com;", patched)

    def test_idempotent_when_host_present(self):
        policy = "default-src 'self'; font-src 'self' data: fonts.gstatic.com; connect-src 'self';"
        self.assertEqual(ensure_google_fonts_font_src(policy), policy)

    def test_noop_without_font_src(self):
        policy = "default-src 'self'; connect-src 'self';"
        self.assertEqual(ensure_font_src_host(policy, "fonts.gstatic.com"), policy)


class EnsureConnectSrcHostTests(SimpleTestCase):
    def test_adds_host_to_connect_src(self):
        policy = "default-src 'self'; connect-src 'self' https://gamma-api.polymarket.com;"
        patched = ensure_iconify_connect_src(policy)
        self.assertIn(
            "connect-src 'self' https://gamma-api.polymarket.com https://api.unisvg.com;",
            patched,
        )

    def test_idempotent_when_host_present(self):
        policy = (
            "default-src 'self'; "
            "connect-src 'self' https://api.unisvg.com;"
        )
        self.assertEqual(ensure_iconify_connect_src(policy), policy)

    def test_idempotent_when_bare_host_present(self):
        policy = "default-src 'self'; connect-src 'self' api.unisvg.com;"
        self.assertEqual(ensure_iconify_connect_src(policy), policy)

    def test_noop_without_connect_src(self):
        policy = "default-src 'self'; font-src 'self' data:;"
        self.assertEqual(
            ensure_connect_src_host(policy, "https://api.unisvg.com"), policy
        )
