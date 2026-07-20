"""Tests for Cloudflare Turnstile human verification."""

from unittest.mock import MagicMock, patch

from django.test import RequestFactory, TestCase, override_settings

from accounts.human_verification import TurnstileHumanVerificationProvider


class TurnstileHumanVerificationTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.provider = TurnstileHumanVerificationProvider()

    @override_settings(
        HUMAN_VERIFICATION_PROVIDER="turnstile",
        TURNSTILE_SECRET_KEY="test-secret",
        HUMAN_VERIFICATION_REQUIRED=True,
    )
    @patch("requests.post")
    def test_siteverify_uses_forwarded_client_ip(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"success": True})
        request = self.factory.post(
            "/accounts/signup/",
            HTTP_X_FORWARDED_FOR="203.0.113.10, 10.0.0.1",
            REMOTE_ADDR="10.0.0.1",
        )

        result = self.provider.verify(token="turnstile-token", request=request)

        self.assertTrue(result.passed)
        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs["data"]
        self.assertEqual(payload["secret"], "test-secret")
        self.assertEqual(payload["response"], "turnstile-token")
        self.assertEqual(payload["remoteip"], "203.0.113.10")

    @override_settings(
        HUMAN_VERIFICATION_PROVIDER="turnstile",
        TURNSTILE_SECRET_KEY="test-secret",
        HUMAN_VERIFICATION_REQUIRED=True,
    )
    @patch("requests.post")
    def test_siteverify_omits_remoteip_when_unavailable(self, mock_post):
        mock_post.return_value = MagicMock(json=lambda: {"success": True})
        request = self.factory.post("/accounts/signup/", REMOTE_ADDR="")

        result = self.provider.verify(token="turnstile-token", request=request)

        self.assertTrue(result.passed)
        payload = mock_post.call_args.kwargs["data"]
        self.assertNotIn("remoteip", payload)

    @override_settings(
        HUMAN_VERIFICATION_PROVIDER="turnstile",
        TURNSTILE_SECRET_KEY="test-secret",
        HUMAN_VERIFICATION_REQUIRED=True,
    )
    def test_missing_token_blocks_when_required(self):
        request = self.factory.post("/accounts/signup/")

        result = self.provider.verify(token="", request=request)

        self.assertFalse(result.passed)
        self.assertEqual(result.detail.get("reason"), "missing secret or token")
