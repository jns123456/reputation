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
        CONTENT_SECURITY_POLICY="default-src 'self'",
    )
    def test_report_only_header_when_enabled(self):
        request = self.factory.get("/")
        response = self.middleware(request)
        self.assertEqual(
            response["Content-Security-Policy-Report-Only"],
            "default-src 'self'",
        )
