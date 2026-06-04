from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

from config.deploy_checks import (
    INSECURE_EAS_OFFCHAIN_SIGNING_KEY,
    INSECURE_SECRET_KEY,
    validate_production_settings,
)


class ValidateProductionSettingsTests(SimpleTestCase):
    def _strong_key(self):
        return "x" * 50

    def _eas_key(self):
        return "y" * 50

    def _call(self, **kwargs):
        defaults = {
            "debug": False,
            "secret_key": self._strong_key(),
            "eas_offchain_signing_key": self._eas_key(),
            "email_verification_dev_show_link": False,
        }
        defaults.update(kwargs)
        validate_production_settings(**defaults)

    def test_skips_when_debug(self):
        self._call(
            debug=True,
            secret_key=INSECURE_SECRET_KEY,
            eas_offchain_signing_key=INSECURE_SECRET_KEY,
            email_verification_dev_show_link=True,
        )

    def test_skips_when_running_tests(self):
        self._call(
            secret_key=INSECURE_SECRET_KEY,
            eas_offchain_signing_key=INSECURE_SECRET_KEY,
            email_verification_dev_show_link=True,
            running_tests=True,
        )

    def test_rejects_insecure_default_secret_key(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            self._call(secret_key=INSECURE_SECRET_KEY)
        self.assertIn("SECRET_KEY", str(ctx.exception))

    def test_rejects_short_secret_key(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            self._call(secret_key="too-short")
        self.assertIn("SECRET_KEY", str(ctx.exception))

    def test_rejects_eas_key_reusing_secret_key(self):
        key = self._strong_key()
        with self.assertRaises(ImproperlyConfigured) as ctx:
            self._call(secret_key=key, eas_offchain_signing_key=key)
        self.assertIn("EAS_OFFCHAIN_SIGNING_KEY", str(ctx.exception))

    def test_rejects_insecure_eas_placeholder(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            self._call(eas_offchain_signing_key=INSECURE_EAS_OFFCHAIN_SIGNING_KEY)
        self.assertIn("EAS_OFFCHAIN_SIGNING_KEY", str(ctx.exception))

    def test_rejects_short_eas_key(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            self._call(eas_offchain_signing_key="too-short")
        self.assertIn("EAS_OFFCHAIN_SIGNING_KEY", str(ctx.exception))

    def test_rejects_dev_verification_link_in_production(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            self._call(email_verification_dev_show_link=True)
        self.assertIn("EMAIL_VERIFICATION_DEV_SHOW_LINK", str(ctx.exception))

    def test_passes_with_safe_production_settings(self):
        self._call()
