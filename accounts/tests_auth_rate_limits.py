"""Rate limits for login/signup, safe redirects, and DRF throttling."""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.http_utils import safe_redirect_to_referer
from accounts.models import AbuseEvent

User = get_user_model()


class LoginRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()
        User.objects.create_user(username="alice", email="a@test.com", password="pass12345")

    @override_settings(ABUSE_RATE_LIMITS={"login": {"ip": (2, 900)}})
    def test_login_blocked_after_limit(self):
        url = reverse("accounts:login")
        for _ in range(2):
            response = self.client.post(url, {"username": "alice", "password": "wrong"})
            self.assertEqual(response.status_code, 200)

        response = self.client.post(url, {"username": "alice", "password": "wrong"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Too many login attempts")
        self.assertTrue(
            AbuseEvent.objects.filter(event_type=AbuseEvent.EventType.RATE_LIMITED).exists()
        )


class SignupEmailUniquenessTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_signup_rejects_duplicate_email(self):
        from accounts.forms import SignUpForm
        from accounts.models import User

        User.objects.create_user(
            username="orig", email="taken@test.com", password="ComplexPass123!"
        )
        form = SignUpForm(
            data={
                "username": "copycat",
                "email": "TAKEN@test.com",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)


class RegistrationRateLimitTests(TestCase):
    def setUp(self):
        cache.clear()

    @override_settings(ABUSE_RATE_LIMITS={"registration": {"ip": (1, 3600)}})
    def test_signup_blocked_after_limit(self):
        url = reverse("accounts:signup")
        payload = {
            "username": "newbie",
            "email": "newbie@test.com",
            "password1": "ComplexPass123!",
            "password2": "ComplexPass123!",
        }
        first = Client()
        response = first.post(url, payload)
        self.assertEqual(response.status_code, 302)

        second = Client()
        response = second.post(
            url,
            {
                "username": "newbie2",
                "email": "newbie2@test.com",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Too many sign-up attempts")


class SafeRedirectTests(TestCase):
    def test_rejects_external_referer(self):
        request = self.client.request().wsgi_request
        request.META["HTTP_REFERER"] = "https://evil.example/phish"
        response = safe_redirect_to_referer(request, fallback="/safe/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/safe/")

    def test_allows_same_host_referer(self):
        request = self.client.get("/").wsgi_request
        referer = request.build_absolute_uri("/markets/")
        request.META["HTTP_REFERER"] = referer
        response = safe_redirect_to_referer(request, fallback="/")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, referer)


class DRFThrottleConfigTests(TestCase):
    def test_rest_framework_throttle_defaults(self):
        from rest_framework.settings import api_settings
        from rest_framework.throttling import AnonRateThrottle, UserRateThrottle

        api_settings.reload()
        self.assertIn(AnonRateThrottle, api_settings.DEFAULT_THROTTLE_CLASSES)
        self.assertIn(UserRateThrottle, api_settings.DEFAULT_THROTTLE_CLASSES)
        self.assertEqual(api_settings.DEFAULT_THROTTLE_RATES["anon"], "120/hour")
        self.assertEqual(api_settings.DEFAULT_THROTTLE_RATES["user"], "600/hour")

    def test_anon_throttle_limits_burst(self):
        from django.contrib.auth.models import AnonymousUser
        from rest_framework.test import APIRequestFactory
        from rest_framework.throttling import AnonRateThrottle

        cache.clear()
        factory = APIRequestFactory()
        request = factory.get("/api/markets/")
        request.user = AnonymousUser()

        throttle = AnonRateThrottle()
        throttle.rate = "2/minute"
        throttle.num_requests, throttle.duration = throttle.parse_rate(throttle.rate)

        class DummyView:
            pass

        view = DummyView()
        self.assertTrue(throttle.allow_request(request, view))
        self.assertTrue(throttle.allow_request(request, view))
        self.assertFalse(throttle.allow_request(request, view))
