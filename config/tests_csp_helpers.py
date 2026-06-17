"""Tests for CSP helper utilities."""

from django.test import SimpleTestCase

from config.csp_helpers import (
    ensure_connect_src_host,
    ensure_font_src_host,
    ensure_frame_src_host,
    ensure_google_fonts_font_src,
    ensure_iconify_connect_src,
    ensure_turnstile_frame_src,
    sanitize_malformed_connect_src,
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

    def test_iconify_api_hosts_allowed_in_connect_src(self):
        from config.settings import build_content_security_policy

        policy = build_content_security_policy()
        connect_part = policy.split("connect-src")[1].split(";")[0]
        self.assertIn("https://api.iconify.design", connect_part)
        self.assertIn("https://api.simplesvg.com", connect_part)
        self.assertIn("https://api.unisvg.com", connect_part)
        self.assertNotIn("https://https://", connect_part)


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


class SanitizeMalformedConnectSrcTests(SimpleTestCase):
    def test_strips_double_scheme_urls(self):
        policy = (
            "connect-src 'self' https://https://api.unisvg.com "
            "https://api.iconify.design;"
        )
        cleaned = sanitize_malformed_connect_src(policy)
        self.assertNotIn("https://https://", cleaned)
        self.assertIn("https://api.unisvg.com", cleaned)

    def test_noop_when_clean(self):
        policy = "connect-src 'self' https://api.unisvg.com;"
        self.assertEqual(sanitize_malformed_connect_src(policy), policy)


class EnsureConnectSrcHostTests(SimpleTestCase):
    def test_adds_host_to_connect_src(self):
        policy = "default-src 'self'; connect-src 'self' https://gamma-api.polymarket.com;"
        patched = ensure_iconify_connect_src(policy)
        self.assertIn("https://api.simplesvg.com", patched)
        self.assertIn("https://api.iconify.design", patched)
        self.assertIn("https://api.unisvg.com", patched)

    def test_idempotent_when_host_present(self):
        policy = (
            "default-src 'self'; "
            "connect-src 'self' https://api.simplesvg.com https://api.iconify.design "
            "https://api.unisvg.com;"
        )
        self.assertEqual(ensure_iconify_connect_src(policy), policy)

    def test_noop_without_connect_src(self):
        policy = "default-src 'self'; font-src 'self' data:;"
        self.assertEqual(ensure_connect_src_host(policy, "api.simplesvg.com"), policy)
