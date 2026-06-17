from django.test import RequestFactory, SimpleTestCase, override_settings

from config.security_middleware import ContentSecurityPolicyMiddleware


class ContentSecurityPolicyMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = ContentSecurityPolicyMiddleware(
            lambda request: __import__("django.http", fromlist=["HttpResponse"]).HttpResponse("ok")
        )

    @override_settings(CSP_ENABLED=False, CONTENT_SECURITY_POLICY="default-src 'self'")
    def test_no_header_when_disabled(self):
        request = self.factory.get("/")
        response = self.middleware(request)
        self.assertNotIn("Content-Security-Policy", response)
        self.assertNotIn("Content-Security-Policy-Report-Only", response)

    @override_settings(
        CSP_ENABLED=True,
        CSP_REPORT_ONLY=True,
        CONTENT_SECURITY_POLICY="default-src 'self'; report-uri https://example.test/csp;",
    )
    def test_report_only_header_when_enabled(self):
        request = self.factory.get("/")
        response = self.middleware(request)
        self.assertIn("report-uri https://example.test/csp;", response["Content-Security-Policy-Report-Only"])

    @override_settings(
        CSP_ENABLED=True,
        CSP_REPORT_ONLY=True,
        CONTENT_SECURITY_POLICY=(
            "default-src 'self'; frame-src 'self' embed.polymarket.com; connect-src 'self';"
        ),
    )
    def test_turnstile_host_added_to_frame_src(self):
        request = self.factory.get("/")
        response = self.middleware(request)
        header = response["Content-Security-Policy-Report-Only"]
        self.assertIn("frame-src 'self' embed.polymarket.com challenges.cloudflare.com;", header)

    @override_settings(
        CSP_ENABLED=True,
        CSP_REPORT_ONLY=True,
        CONTENT_SECURITY_POLICY=(
            "default-src 'self'; font-src 'self' data:; connect-src 'self';"
        ),
    )
    def test_google_fonts_host_added_to_font_src(self):
        request = self.factory.get("/")
        response = self.middleware(request)
        header = response["Content-Security-Policy-Report-Only"]
        self.assertIn("font-src 'self' data: fonts.gstatic.com;", header)

    @override_settings(
        CSP_ENABLED=True,
        CSP_REPORT_ONLY=True,
        CONTENT_SECURITY_POLICY=(
            "default-src 'self'; connect-src 'self' https://gamma-api.polymarket.com;"
        ),
    )
    def test_iconify_unisvg_host_added_to_connect_src(self):
        request = self.factory.get("/")
        response = self.middleware(request)
        header = response["Content-Security-Policy-Report-Only"]
        self.assertIn(
            "connect-src 'self' https://gamma-api.polymarket.com https://api.unisvg.com;",
            header,
        )
