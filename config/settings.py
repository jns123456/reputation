import os
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

import environ
import ssl

from config.deploy_checks import validate_production_settings
from config.media_storage import resolve_s3_media_settings

# ``manage.py test`` / pytest should not require a local Redis for Django cache.
_RUNNING_TESTS = "test" in sys.argv or "pytest" in sys.argv[0]

from celery.schedules import crontab, schedule

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, True),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)

environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = env("SECRET_KEY", default="django-insecure-dev-key-change-in-production")
DEBUG = env("DEBUG")
# Set DJANGO_ENV=production in deployed environments so deploy checks can
# reject DEBUG=True (which would silently disable HTTPS/HSTS/secure cookies).
DJANGO_ENV = env("DJANGO_ENV", default="development")
# Django admin mount point. Override in production with a non-guessable path
# (e.g. ADMIN_URL_PATH=ops-7f3a9c/) to cut credential-stuffing noise.
ADMIN_URL_PATH = env("ADMIN_URL_PATH", default="admin/").lstrip("/")
if not ADMIN_URL_PATH.endswith("/"):
    ADMIN_URL_PATH += "/"
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
if not CSRF_TRUSTED_ORIGINS and not DEBUG:
    CSRF_TRUSTED_ORIGINS = [
        f"https://{host}"
        for host in ALLOWED_HOSTS
        if host and host not in ("*", "localhost", "127.0.0.1") and not host.startswith(".")
    ]
DEV_FAST_MODE = env.bool("DEV_FAST_MODE", default=False)
NAV_BADGE_CACHE_SECONDS = env.int("NAV_BADGE_CACHE_SECONDS", default=60)
LEADERBOARD_CACHE_SECONDS = env.int("LEADERBOARD_CACHE_SECONDS", default=120)
WORLD_CUP_MATCHES_PER_PAGE = env.int("WORLD_CUP_MATCHES_PER_PAGE", default=24)
CATEGORY_BROWSE_PAGE_SIZE = env.int("CATEGORY_BROWSE_PAGE_SIZE", default=24)
MARKET_LIST_PAGE_SIZE = env.int("MARKET_LIST_PAGE_SIZE", default=24)
EAS_ATTESTER_ID = env("EAS_ATTESTER_ID", default="proofrep-platform-v1")
EAS_OFFCHAIN_SIGNING_KEY = env("EAS_OFFCHAIN_SIGNING_KEY", default=SECRET_KEY)
EAS_CHAIN_ID = env.int("EAS_CHAIN_ID", default=0)
EAS_VERIFYING_CONTRACT = env("EAS_VERIFYING_CONTRACT", default="")
EAS_DAILY_BATCH_ENABLED = env.bool("EAS_DAILY_BATCH_ENABLED", default=True)
EAS_DAILY_BATCH_HOUR_UTC = env.int("EAS_DAILY_BATCH_HOUR_UTC", default=0)
EAS_ONCHAIN_ANCHOR_ENABLED = env.bool("EAS_ONCHAIN_ANCHOR_ENABLED", default=False)
EAS_ANCHOR_WALLET_ADDRESS = env("EAS_ANCHOR_WALLET_ADDRESS", default="")
EAS_ANCHOR_PRIVATE_KEY = env("EAS_ANCHOR_PRIVATE_KEY", default="")
EAS_BASE_RPC_URL = env("EAS_BASE_RPC_URL", default="https://mainnet.base.org")
EAS_CONTRACT_ADDRESS = env(
    "EAS_CONTRACT_ADDRESS",
    default="0x4200000000000000000000000000000000000021",
)
EAS_SCHEMA_REGISTRY_ADDRESS = env(
    "EAS_SCHEMA_REGISTRY_ADDRESS",
    default="0x4200000000000000000000000000000000000020",
)
# Base developer portal domain verification (meta name="base:app_id" in <head>).
BASE_APP_ID = env("BASE_APP_ID", default="")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "api",
    "accounts",
    "markets",
    "predictions",
    "comments",
    "reputation",
    "integrations",
    "dashboard",
    "challenges",
    "pulse",
    "mcp",
    "messaging",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "config.request_id_middleware.RequestIdMiddleware",
    "config.security_middleware.ContentSecurityPolicyMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "accounts.middleware.ClientTimezoneMiddleware",
    "accounts.middleware.CountryLanguageMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "accounts.middleware.EmailVerificationRequiredMiddleware",
    "accounts.middleware.ProfileSetupRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": not DEV_FAST_MODE,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "accounts.context_processors.notification_context",
                "accounts.context_processors.auth0_context",
                "challenges.context_processors.challenge_context",
                "config.context_processors.static_version",
                "config.context_processors.platform_context",
                "markets.tape_context.tape_markets_context",
            ],
        },
    },
]

if DEV_FAST_MODE:
    TEMPLATES[0]["OPTIONS"]["loaders"] = [
        (
            "django.template.loaders.cached.Loader",
            [
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
        ),
    ]
elif DEBUG:
    TEMPLATES[0]["OPTIONS"]["context_processors"].insert(
        0,
        "django.template.context_processors.debug",
    )

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}

if not DEBUG:
    DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=600)
    DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
    # Behind a TLS-terminating proxy (Heroku/AWS) Django sees the request as HTTP.
    # Trust the proxy's protocol header so request.build_absolute_uri() yields
    # https:// — required for the Auth0 callback URL to match and be accepted.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
    SECURE_REFERRER_POLICY = env("SECURE_REFERRER_POLICY", default="same-origin")
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = True
    CSRF_COOKIE_SAMESITE = "Lax"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "accounts.User"

LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

LANGUAGES = [
    ("en", "English"),
    ("es", "Español"),
]

LOCALE_PATHS = [BASE_DIR / "locale"]

# Optional path to MaxMind GeoLite2-Country.mmdb for IP → country (see .env.example).
GEOIP_COUNTRY_PATH = env("GEOIP_COUNTRY_PATH", default="")
# Optional GeoLite2-City.mmdb for IP → IANA timezone (more accurate than country fallback).
GEOIP_CITY_PATH = env("GEOIP_CITY_PATH", default="")
# When GeoLite2 is not configured, resolve country/timezone via ipwho.is (cached 24h).
GEOIP_HTTP_FALLBACK_ENABLED = env.bool(
    "GEOIP_HTTP_FALLBACK_ENABLED",
    default=not _RUNNING_TESTS,
)

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
# Django 5.1+ ignores the legacy STATICFILES_STORAGE setting — storage backends
# must be configured via STORAGES. In production, WhiteNoise's manifest storage
# fingerprints filenames so assets can be served with far-future, immutable cache
# headers (large win on repeat visits); hashed files get 1y/immutable and the rest
# get WHITENOISE_MAX_AGE.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}
if not DEBUG:
    WHITENOISE_MAX_AGE = env.int("WHITENOISE_MAX_AGE", default=86400)

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Pulse image uploads — local disk in dev; S3-compatible storage in production (Cloudflare R2 recommended).
# Profile avatars are generated (DiceBear) and never use this bucket.
USE_S3_MEDIA = env.bool("USE_S3_MEDIA", default=bool(env("AWS_STORAGE_BUCKET_NAME", default="")))
if USE_S3_MEDIA:
    INSTALLED_APPS.append("storages")
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
    _media_storage = resolve_s3_media_settings(
        bucket_name=env("AWS_STORAGE_BUCKET_NAME"),
        endpoint_url=env("AWS_S3_ENDPOINT_URL", default=""),
        region_name=env("AWS_S3_REGION_NAME", default=""),
        custom_domain=env("AWS_S3_CUSTOM_DOMAIN", default=""),
        default_acl=env("AWS_DEFAULT_ACL", default=None),
        running_tests=_RUNNING_TESTS,
    )
    globals().update(_media_storage)
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
        },
        "staticfiles": {
            "BACKEND": (
                "django.contrib.staticfiles.storage.StaticFilesStorage"
                if DEBUG
                else "whitenoise.storage.CompressedStaticFilesStorage"
            ),
        },
    }

PULSE_MAX_IMAGE_BYTES = env.int("PULSE_MAX_IMAGE_BYTES", default=5 * 1024 * 1024)

# Deterministic profile avatars (no storage) — https://www.dicebear.com/
AVATAR_DICEBEAR_BASE_URL = env("AVATAR_DICEBEAR_BASE_URL", default="https://api.dicebear.com/9.x")
AVATAR_DICEBEAR_STYLE = env("AVATAR_DICEBEAR_STYLE", default="identicon")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Email / engagement notifications --------------------------------------------
# Absolute base URL used to build links inside emails (no request available in tasks).
SITE_BASE_URL = env("SITE_BASE_URL", default="http://localhost:8000")
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default=(
        "django.core.mail.backends.console.EmailBackend"
        if DEBUG
        else "django.core.mail.backends.smtp.EmailBackend"
    ),
)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="PredictStamp <no-reply@predictstamp.app>")
SERVER_EMAIL = env("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)

# Email verification (signup + email changes) --------------------------------
EMAIL_VERIFICATION_REQUIRED = env.bool("EMAIL_VERIFICATION_REQUIRED", default=True)
EMAIL_VERIFICATION_TOKEN_HOURS = env.int("EMAIL_VERIFICATION_TOKEN_HOURS", default=48)
EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS = env.int(
    "EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS",
    default=60,
)
# In DEBUG, show a clickable verify link on the pending page when Resend rejects (e.g. onboarding@resend.dev).
EMAIL_VERIFICATION_DEV_SHOW_LINK = env.bool(
    "EMAIL_VERIFICATION_DEV_SHOW_LINK",
    default=DEBUG,
)

# Heroku Mailgun add-on exposes MAILGUN_SMTP_* — wire it when EMAIL_HOST is unset.
_mailgun_smtp = env("MAILGUN_SMTP_SERVER", default="")
if _mailgun_smtp and not EMAIL_HOST:
    EMAIL_HOST = _mailgun_smtp
    EMAIL_PORT = env.int("MAILGUN_SMTP_PORT", default=587)
    EMAIL_HOST_USER = env("MAILGUN_SMTP_LOGIN", default="")
    EMAIL_HOST_PASSWORD = env("MAILGUN_SMTP_PASSWORD", default="")
    EMAIL_USE_TLS = True
    _mailgun_domain = env("MAILGUN_DOMAIN", default="")
    if _mailgun_domain and DEFAULT_FROM_EMAIL == "PredictStamp <no-reply@predictstamp.app>":
        DEFAULT_FROM_EMAIL = f"PredictStamp <noreply@{_mailgun_domain}>"
        SERVER_EMAIL = DEFAULT_FROM_EMAIL
# Master switch for outbound engagement emails (transactional + digest + streak).
ENGAGEMENT_EMAILS_ENABLED = env.bool("ENGAGEMENT_EMAILS_ENABLED", default=True)
# Resend.com API — simplest production email (no SMTP). Free tier: 100 emails/day.
# Sign up at https://resend.com/api-keys — use onboarding@resend.dev until domain is verified.
RESEND_API_KEY = env("RESEND_API_KEY", default="")
RESEND_FROM_EMAIL = env(
    "RESEND_FROM_EMAIL",
    default="PredictStamp <onboarding@resend.dev>",
)

# Tests must never hit a real provider: use the in-memory backend and capture
# everything in ``mail.outbox`` regardless of any RESEND/SMTP creds in .env.
# A sentinel EMAIL_HOST keeps delivery "configured" so opt-in send paths run
# (the test runner forces DEBUG=False, disabling the console fallback).
if _RUNNING_TESTS:
    EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    RESEND_API_KEY = ""
    EMAIL_HOST = "localhost"
    _mailgun_smtp = ""

# Web Push (PWA) ---------------------------------------------------------------
# VAPID keys: generate once with `vapid --gen` (py-vapid) or
# `.venv/bin/python -c "from py_vapid import Vapid01; v=Vapid01(); v.generate_keys(); ..."`.
# Public key is the URL-safe base64 (applicationServerKey) handed to the browser.
VAPID_PUBLIC_KEY = env("VAPID_PUBLIC_KEY", default="")
VAPID_PRIVATE_KEY = env("VAPID_PRIVATE_KEY", default="")
VAPID_CLAIMS_EMAIL = env("VAPID_CLAIMS_EMAIL", default="mailto:admin@predictstamp.app")
# Push is inert unless both keys are configured — keeps dev/CI clean.
WEBPUSH_ENABLED = bool(VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY)
if _RUNNING_TESTS:
    WEBPUSH_ENABLED = False

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "dashboard:landing"

# Auth0 (Universal Login) -----------------------------------------------------
# Optional, additive social/OIDC login alongside the local username/password
# flow. The "Continue with Auth0" button only appears when all three values are
# configured (see ``AUTH0_ENABLED``). Auth0 already verifies email ownership, so
# users who arrive through it skip the local email-verification step.
AUTH0_DOMAIN = env("AUTH0_DOMAIN", default="")
AUTH0_CLIENT_ID = env("AUTH0_CLIENT_ID", default="")
AUTH0_CLIENT_SECRET = env("AUTH0_CLIENT_SECRET", default="")
# Optional API audience if you later need Auth0-issued access tokens.
AUTH0_AUDIENCE = env("AUTH0_AUDIENCE", default="")
# Auth0 connection name for Google (Dashboard → Authentication → Social → Google).
AUTH0_GOOGLE_CONNECTION = env("AUTH0_GOOGLE_CONNECTION", default="google-oauth2")
AUTH0_ENABLED = bool(AUTH0_DOMAIN and AUTH0_CLIENT_ID and AUTH0_CLIENT_SECRET)

_redis_url = env("REDIS_URL", default="redis://localhost:6379/0")
USE_REDIS_CACHE = env.bool("USE_REDIS_CACHE", default=not DEBUG)

# Connection resilience: managed Redis (Heroku) silently drops idle TCP/TLS
# sockets, surfacing as "Connection reset by peer" / "UNEXPECTED_EOF". Health
# checks revalidate pooled connections before use and keepalive + timeouts let
# dropped sockets fail fast and reconnect instead of hanging.
REDIS_HEALTH_CHECK_INTERVAL = env.int("REDIS_HEALTH_CHECK_INTERVAL", default=30)
REDIS_SOCKET_TIMEOUT = env.float("REDIS_SOCKET_TIMEOUT", default=5.0)
REDIS_SOCKET_CONNECT_TIMEOUT = env.float("REDIS_SOCKET_CONNECT_TIMEOUT", default=5.0)

CELERY_BROKER_URL = _redis_url
CELERY_RESULT_BACKEND = _redis_url
CELERY_BROKER_CONNECTION_TIMEOUT = env.float("CELERY_BROKER_CONNECTION_TIMEOUT", default=0.5)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = False
# Recover from mid-run broker disconnects (the failure seen in production) by
# retrying the connection instead of failing the task.
CELERY_BROKER_CONNECTION_RETRY = True
CELERY_BROKER_CONNECTION_MAX_RETRIES = env.int("CELERY_BROKER_CONNECTION_MAX_RETRIES", default=3)
# Redis Mini caps connections at 20 (shared web + worker + beat); keep the pool small.
CELERY_BROKER_POOL_LIMIT = env.int("CELERY_BROKER_POOL_LIMIT", default=5)
CELERY_REDIS_RETRY_ON_TIMEOUT = True
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "socket_keepalive": True,
    "socket_timeout": REDIS_SOCKET_TIMEOUT,
    "socket_connect_timeout": REDIS_SOCKET_CONNECT_TIMEOUT,
    "health_check_interval": REDIS_HEALTH_CHECK_INTERVAL,
}
CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS = dict(CELERY_BROKER_TRANSPORT_OPTIONS)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
if _RUNNING_TESTS:
    # Run tasks in-process so ``.delay()`` never needs a local Redis broker.
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True

# Heroku Redis uses rediss:// with self-signed certs, so verification must stay
# off there (REDIS_TLS_VERIFY=False, the default). On providers with CA-backed
# certs (AWS ElastiCache, Redis Cloud, etc.) set REDIS_TLS_VERIFY=True to
# protect the Redis path against MITM.
REDIS_TLS_VERIFY = env.bool("REDIS_TLS_VERIFY", default=False)
_redis_ssl_cert_reqs = ssl.CERT_REQUIRED if REDIS_TLS_VERIFY else ssl.CERT_NONE
if _redis_url.startswith("rediss://"):
    _redis_ssl = {"ssl_cert_reqs": _redis_ssl_cert_reqs}
    CELERY_BROKER_USE_SSL = _redis_ssl
    CELERY_REDIS_BACKEND_USE_SSL = _redis_ssl

if _redis_url and USE_REDIS_CACHE:
    redis_url = _redis_url
    redis_cache_options = {
        "socket_keepalive": True,
        "socket_timeout": REDIS_SOCKET_TIMEOUT,
        "socket_connect_timeout": REDIS_SOCKET_CONNECT_TIMEOUT,
        "health_check_interval": REDIS_HEALTH_CHECK_INTERVAL,
        "retry_on_timeout": True,
    }
    if redis_url.startswith("rediss://"):
        redis_cache_options["ssl_cert_reqs"] = (
            _redis_ssl_cert_reqs if REDIS_TLS_VERIFY else None
        )
    CACHES = {
        "default": {
            "BACKEND": "config.cache_backends.ResilientRedisCache",
            "LOCATION": redis_url,
            "OPTIONS": redis_cache_options,
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "reputation-cache",
        }
    }

if _RUNNING_TESTS:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "reputation-test-cache",
        }
    }

POLYMARKET_ECONOMY_CACHE_SECONDS = env.int("POLYMARKET_ECONOMY_CACHE_SECONDS", default=300)
MARKET_SYNC_CACHE_SECONDS = env.int("MARKET_SYNC_CACHE_SECONDS", default=POLYMARKET_ECONOMY_CACHE_SECONDS)
MARKET_SYNC_CATEGORY_LIMIT = env.int("MARKET_SYNC_CATEGORY_LIMIT", default=100)
MARKET_LIST_SORTED_LIMIT = env.int("MARKET_LIST_SORTED_LIMIT", default=200)
POLYMARKET_TOP_VOLUME_MIN_SHARE = env.float("POLYMARKET_TOP_VOLUME_MIN_SHARE", default=0.5)
POLYMARKET_TOP_VOLUME_MAX_MARKETS = env.int("POLYMARKET_TOP_VOLUME_MAX_MARKETS", default=500)
POLYMARKET_TOP_VOLUME_MAX_EVENT_PAGES = env.int("POLYMARKET_TOP_VOLUME_MAX_EVENT_PAGES", default=15)
POLYMARKET_TAG_SYNC_MAX_EVENT_PAGES = env.int("POLYMARKET_TAG_SYNC_MAX_EVENT_PAGES", default=10)
MARKET_FULL_SYNC_INTERVAL_HOURS = env.int("MARKET_FULL_SYNC_INTERVAL_HOURS", default=6)
MARKET_STALE_SYNC_INTERVAL_MINUTES = env.int("MARKET_STALE_SYNC_INTERVAL_MINUTES", default=10)
ENABLE_EMBEDDED_MARKET_SYNC = env.bool("ENABLE_EMBEDDED_MARKET_SYNC", default=False)
# 0 = import every available World Cup group-stage match from Polymarket.
WORLD_CUP_MATCH_SYNC_LIMIT = env.int("WORLD_CUP_MATCH_SYNC_LIMIT", default=0)
# 0 = import every available H2H match (tennis, NBA, etc.) from Polymarket.
H2H_MATCH_SYNC_LIMIT = env.int("H2H_MATCH_SYNC_LIMIT", default=0)
F1_MARKET_SYNC_LIMIT = env.int("F1_MARKET_SYNC_LIMIT", default=0)
MARKET_SYNC_STALE_MINUTES = env.int("MARKET_SYNC_STALE_MINUTES", default=10)
MARKET_SYNC_STALE_BATCH_SIZE = env.int("MARKET_SYNC_STALE_BATCH_SIZE", default=100)
MARKET_TRANSLATION_ENABLED = env.bool("MARKET_TRANSLATION_ENABLED", default=False)
if _RUNNING_TESTS:
    # Never call MyMemory/DeepL during tests (avoids live HTTP + macOS SSL issues).
    MARKET_TRANSLATION_ENABLED = False
MARKET_TRANSLATION_CACHE_SECONDS = env.int("MARKET_TRANSLATION_CACHE_SECONDS", default=60 * 60 * 24 * 30)
MARKET_TRANSLATION_REQUEST_DELAY = env.float("MARKET_TRANSLATION_REQUEST_DELAY", default=0.35)
DEEPL_AUTH_KEY = env("DEEPL_AUTH_KEY", default="")
DEEPL_API_URL = env("DEEPL_API_URL", default="https://api-free.deepl.com/v2/translate")
CATEGORY_SYNC_FAILURE_COOLDOWN_SECONDS = env.int(
    "CATEGORY_SYNC_FAILURE_COOLDOWN_SECONDS",
    default=120,
)

REST_FRAMEWORK = {
    # Bearer tokens (MCP credentials) + session cookies. BasicAuth is excluded
    # so attackers cannot brute-force passwords against /api/ endpoints.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api.authentication.McpBearerAuthentication",
        "api.authentication.ApiSessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "120/hour",
        "user": "600/hour",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "api.exceptions.api_exception_handler",
}

API_WRITES_ENABLED = env.bool("API_WRITES_ENABLED", default=True)
# OpenAPI/Swagger/ReDoc: public in DEBUG; staff-only in production (tests stay public).
API_OPENAPI_STAFF_ONLY = env.bool(
    "API_OPENAPI_STAFF_ONLY",
    default=(not DEBUG and not _RUNNING_TESTS),
)

SPECTACULAR_SETTINGS = {
    "TITLE": "PredictStamp API",
    "DESCRIPTION": (
        "REST API for markets, forecasts, reputation, forum, and challenges. "
        "Authenticate with session cookies or Bearer tokens minted at /mcp/tokens/."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
}

# --- Anti-abuse & human verification (AGENTS.md §16) -------------------------
# Pluggable human-verification provider: "noop" (default) or "turnstile".
HUMAN_VERIFICATION_PROVIDER = env("HUMAN_VERIFICATION_PROVIDER", default="noop")
HUMAN_VERIFICATION_REQUIRED = env.bool("HUMAN_VERIFICATION_REQUIRED", default=False)
TURNSTILE_SECRET_KEY = env("TURNSTILE_SECRET_KEY", default="")
TURNSTILE_SITE_KEY = env("TURNSTILE_SITE_KEY", default="")
# Optional per-action rate-limit overrides: {action: {tier: (limit, window_seconds)}}.
ABUSE_RATE_LIMITS = {}
# Shared anti-abuse gate for web + MCP write services (``accounts.write_guard``).
ABUSE_WRITE_GUARD_ENABLED = env.bool("ABUSE_WRITE_GUARD_ENABLED", default=True)
if _RUNNING_TESTS:
    # Existing suites assume unlimited writes; write-guard tests opt in explicitly.
    ABUSE_WRITE_GUARD_ENABLED = False

# --- MCP server (AGENTS.md §17) ----------------------------------------------
# Read tools are always available to token holders. Writes are OFF by default and
# gated behind both the master switch and per-tool flags (safe rollout).
MCP_ENABLED = env.bool("MCP_ENABLED", default=True)
MCP_WRITES_ENABLED = env.bool("MCP_WRITES_ENABLED", default=False)
MCP_SUBMIT_PREDICTION_ENABLED = env.bool("MCP_SUBMIT_PREDICTION_ENABLED", default=False)
MCP_SUBMIT_COMMENT_ENABLED = env.bool("MCP_SUBMIT_COMMENT_ENABLED", default=False)
# Circuit breaker: disable a write tool after this many abuse signals in the window.
MCP_CIRCUIT_BREAKER_THRESHOLD = env.int("MCP_CIRCUIT_BREAKER_THRESHOLD", default=25)
MCP_CIRCUIT_BREAKER_WINDOW_SECONDS = env.int("MCP_CIRCUIT_BREAKER_WINDOW_SECONDS", default=300)

# Automatic agent trust promotion (AGENTS.md §15). Runs on a Celery Beat cadence
# when enabled; thresholds are overridable for tuning.
AGENT_TRUST_AUTOPROMOTE_ENABLED = env.bool("AGENT_TRUST_AUTOPROMOTE_ENABLED", default=True)
AGENT_TRUST_PROMOTE_INTERVAL_HOURS = env.int("AGENT_TRUST_PROMOTE_INTERVAL_HOURS", default=6)
AGENT_TRUST_LIMITED_AGE_DAYS = env.int("AGENT_TRUST_LIMITED_AGE_DAYS", default=1)
AGENT_TRUST_STANDARD_AGE_DAYS = env.int("AGENT_TRUST_STANDARD_AGE_DAYS", default=7)
AGENT_TRUST_STANDARD_CONTRIBUTIONS = env.int("AGENT_TRUST_STANDARD_CONTRIBUTIONS", default=5)
AGENT_TRUST_TRUSTED_AGE_DAYS = env.int("AGENT_TRUST_TRUSTED_AGE_DAYS", default=30)
AGENT_TRUST_TRUSTED_CONTRIBUTIONS = env.int("AGENT_TRUST_TRUSTED_CONTRIBUTIONS", default=25)
AGENT_TRUST_ABUSE_BLOCK = env.int("AGENT_TRUST_ABUSE_BLOCK", default=3)
AGENT_TRUST_ABUSE_WINDOW_DAYS = env.int("AGENT_TRUST_ABUSE_WINDOW_DAYS", default=7)

# Reputation scoring defaults
REPUTATION_BASE_POINTS = 10
REPUTATION_BASE_PENALTY = 5
# Minimum scored forecasts in the ranking denominator (anti-luck for low sample).
REPUTATION_SCORE_MIN_SAMPLE = env.int("REPUTATION_SCORE_MIN_SAMPLE", default=3)
# Relative leaderboard: only users with strictly more than this count qualify for rank.
REPUTATION_RELATIVE_MIN_SCORED_FORECASTS = env.int(
    "REPUTATION_RELATIVE_MIN_SCORED_FORECASTS", default=10
)
POPULARITY_UPVOTE_POINTS = 1
POPULARITY_DOWNVOTE_POINTS = -1
POPULARITY_REPOST_POINTS = 1

POLYMARKET_API_URL = env(
    "POLYMARKET_API_URL",
    default="https://gamma-api.polymarket.com",
)

# Scheduled re-engagement emails are OFF by default to keep mailbox volume low
# (and stay within provider quotas). Flip the matching flag to re-enable each one.
DIGEST_EMAILS_ENABLED = env.bool("DIGEST_EMAILS_ENABLED", default=False)
STREAK_REMINDER_EMAILS_ENABLED = env.bool("STREAK_REMINDER_EMAILS_ENABLED", default=False)
MARKET_RESOLVING_REMINDERS_ENABLED = env.bool(
    "MARKET_RESOLVING_REMINDERS_ENABLED", default=False
)
# FIFO compaction of bulky Polymarket JSON on resolved/closed markets (Heroku disk).
MARKET_RAW_PRUNE_ENABLED = env.bool("MARKET_RAW_PRUNE_ENABLED", default=True)
MARKET_RAW_PRUNE_BATCH_SIZE = env.int("MARKET_RAW_PRUNE_BATCH_SIZE", default=500)
MARKET_RAW_PRUNE_HOUR_UTC = env.int("MARKET_RAW_PRUNE_HOUR_UTC", default=4)
# Delete resolved markets with no user history after N days (keeps disk bounded).
MARKET_ORPHAN_RESOLVED_CLEANUP_ENABLED = env.bool(
    "MARKET_ORPHAN_RESOLVED_CLEANUP_ENABLED", default=True
)
MARKET_ORPHAN_RESOLVED_RETENTION_DAYS = env.int(
    "MARKET_ORPHAN_RESOLVED_RETENTION_DAYS", default=30
)
MARKET_ORPHAN_RESOLVED_CLEANUP_BATCH_SIZE = env.int(
    "MARKET_ORPHAN_RESOLVED_CLEANUP_BATCH_SIZE", default=1000
)
MARKET_ORPHAN_RESOLVED_CLEANUP_HOUR_UTC = env.int(
    "MARKET_ORPHAN_RESOLVED_CLEANUP_HOUR_UTC", default=5
)

CELERY_BEAT_SCHEDULE = {
    "sync-all-category-markets": {
        "task": "integrations.tasks.sync_all_category_markets_task",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "refresh-stale-open-markets": {
        "task": "integrations.tasks.refresh_stale_open_markets_task",
        "schedule": schedule(run_every=timedelta(minutes=MARKET_STALE_SYNC_INTERVAL_MINUTES)),
    },
}
if MARKET_RAW_PRUNE_ENABLED:
    CELERY_BEAT_SCHEDULE["prune-market-raw-fifo"] = {
        "task": "markets.tasks.prune_market_raw_fifo_task",
        "schedule": crontab(minute=45, hour=MARKET_RAW_PRUNE_HOUR_UTC),
    }
if MARKET_ORPHAN_RESOLVED_CLEANUP_ENABLED:
    CELERY_BEAT_SCHEDULE["delete-orphan-resolved-markets"] = {
        "task": "markets.tasks.delete_orphan_resolved_markets_task",
        "schedule": crontab(
            minute=15, hour=MARKET_ORPHAN_RESOLVED_CLEANUP_HOUR_UTC
        ),
    }
if EAS_DAILY_BATCH_ENABLED:
    CELERY_BEAT_SCHEDULE["build-daily-attestation-batch"] = {
        "task": "integrations.tasks.build_daily_attestation_batch_task",
        "schedule": crontab(minute=5, hour=EAS_DAILY_BATCH_HOUR_UTC),
    }
# Daily re-engagement digest (newsletter-style summary).
if DIGEST_EMAILS_ENABLED:
    CELERY_BEAT_SCHEDULE["send-daily-digest"] = {
        "task": "accounts.tasks.send_daily_digest_task",
        "schedule": crontab(minute=0, hour=env.int("DIGEST_SEND_HOUR_UTC", default=13)),
    }
# "Your streak ends tonight" reminder for users who haven't acted today.
if STREAK_REMINDER_EMAILS_ENABLED:
    CELERY_BEAT_SCHEDULE["send-streak-risk-reminders"] = {
        "task": "accounts.tasks.send_streak_risk_reminders_task",
        "schedule": crontab(minute=0, hour=env.int("STREAK_REMINDER_HOUR_UTC", default=22)),
    }
# "A market you forecast closes soon" reminder — runs a few times daily.
if MARKET_RESOLVING_REMINDERS_ENABLED:
    CELERY_BEAT_SCHEDULE["send-market-resolving-reminders"] = {
        "task": "accounts.tasks.send_market_resolving_reminders_task",
        "schedule": crontab(minute=15, hour="*/6"),
    }
# Weekly reputation contest — off-platform cash prizes for top weekly finishers.
WEEKLY_CONTEST_ENABLED = env.bool("WEEKLY_CONTEST_ENABLED", default=True)
WEEKLY_CONTEST_PRIZE_USD = env.int("WEEKLY_CONTEST_PRIZE_USD", default=5)
WEEKLY_CONTEST_MIN_SCORED_FORECASTS = env.int("WEEKLY_CONTEST_MIN_SCORED_FORECASTS", default=10)
WEEKLY_CONTEST_FIRST_WEEK_START = env("WEEKLY_CONTEST_FIRST_WEEK_START", default="2026-06-21")
WEEKLY_CONTEST_WINNER_EMAILS_ENABLED = env.bool(
    "WEEKLY_CONTEST_WINNER_EMAILS_ENABLED",
    default=WEEKLY_CONTEST_ENABLED,
)
CONTEST_PAYOUTS_ENABLED = env.bool("CONTEST_PAYOUTS_ENABLED", default=WEEKLY_CONTEST_ENABLED)
CONTEST_PAYOUT_MIN_USD = env.int("CONTEST_PAYOUT_MIN_USD", default=5)
CONTEST_PAYOUT_NOTIFY_EMAIL = env("CONTEST_PAYOUT_NOTIFY_EMAIL", default="juaninappa@gmail.com")
if WEEKLY_CONTEST_ENABLED:
    CELERY_BEAT_SCHEDULE["finalize-previous-weekly-contest"] = {
        "task": "reputation.tasks.finalize_previous_weekly_contest_task",
        "schedule": crontab(minute=15, hour=1, day_of_week=0),
    }
# Quarterly reputation seasons — permanent awards for top finishers.
SEASON_AWARDS_ENABLED = env.bool("SEASON_AWARDS_ENABLED", default=False)
if SEASON_AWARDS_ENABLED:
    CELERY_BEAT_SCHEDULE["finalize-previous-season"] = {
        "task": "reputation.tasks.finalize_previous_season_task",
        "schedule": crontab(minute=30, hour=2),
    }
# Rule-based AI-agent trust promotion (AGENTS.md §15).
if AGENT_TRUST_AUTOPROMOTE_ENABLED:
    CELERY_BEAT_SCHEDULE["promote-agent-trust"] = {
        "task": "accounts.tasks.promote_agent_trust_task",
        "schedule": schedule(
            run_every=timedelta(hours=AGENT_TRUST_PROMOTE_INTERVAL_HOURS)
        ),
    }

# Official Polymarket embed widget — https://embed.polymarket.com/
POLYMARKET_EMBED_BASE_URL = env(
    "POLYMARKET_EMBED_BASE_URL",
    default="https://embed.polymarket.com/market",
)
# Sports match events (e.g. FIFA World Cup 3-way moneyline) use /sports, not /market.
POLYMARKET_SPORTS_EMBED_BASE_URL = env(
    "POLYMARKET_SPORTS_EMBED_BASE_URL",
    default="https://embed.polymarket.com/sports",
)
POLYMARKET_EMBED_THEME = env("POLYMARKET_EMBED_THEME", default="light")
POLYMARKET_EMBED_FEATURES = env(
    "POLYMARKET_EMBED_FEATURES",
    default="chart,volume,liveActivity",
)
POLYMARKET_EMBED_LAYOUT = env("POLYMARKET_EMBED_LAYOUT", default="standard")
POLYMARKET_EMBED_BORDER = env.bool("POLYMARKET_EMBED_BORDER", default=True)
# Polymarket embed defaults to 400px; pass a large width so max-width:100% fills our container.
POLYMARKET_EMBED_CONTENT_WIDTH = env.int("POLYMARKET_EMBED_CONTENT_WIDTH", default=1200)
POLYMARKET_EMBED_WIDTH = env("POLYMARKET_EMBED_WIDTH", default="100%")
POLYMARKET_EMBED_HEIGHT = env.int("POLYMARKET_EMBED_HEIGHT", default=420)


def build_content_security_policy(*, sentry_dsn=""):
    """Pragmatic CSP for Tailwind/HTMX CDN + Polymarket embeds (report-only rollout)."""
    from config.csp_helpers import ICONIFY_CONNECT_HOSTS, sentry_csp_report_uri

    embed_hosts = []
    for url in (POLYMARKET_EMBED_BASE_URL, POLYMARKET_SPORTS_EMBED_BASE_URL):
        host = urlparse(url).netloc
        if host and host not in embed_hosts:
            embed_hosts.append(host)
    embed_src = " ".join(embed_hosts) if embed_hosts else "embed.polymarket.com"
    dicebear_host = urlparse(AVATAR_DICEBEAR_BASE_URL).netloc or "api.dicebear.com"
    api_host = urlparse(POLYMARKET_API_URL).netloc or "gamma-api.polymarket.com"

    connect_hosts = ["'self'", f"https://{api_host}", "https://challenges.cloudflare.com"]
    connect_hosts.extend(f"https://{host}" for host in ICONIFY_CONNECT_HOSTS)
    report_uri = sentry_csp_report_uri(sentry_dsn)
    if report_uri:
        report_host = urlparse(report_uri).hostname
        if report_host:
            connect_hosts.append(f"https://{report_host}")

    policy = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' cdn.tailwindcss.com unpkg.com "
        "cdn.jsdelivr.net code.iconify.design challenges.cloudflare.com; "
        f"frame-src 'self' {embed_src} challenges.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' cdn.tailwindcss.com; "
        f"img-src 'self' data: https: {dicebear_host}; "
        f"connect-src {' '.join(connect_hosts)}; "
        "font-src 'self' data:; "
        "object-src 'none'; "
        "base-uri 'self';"
    )
    if report_uri:
        policy += f" report-uri {report_uri};"
    return policy


# Optional error monitoring — also feeds CSP violation reports when set.
SENTRY_DSN = env("SENTRY_DSN", default="")

CSP_ENABLED = env.bool("CSP_ENABLED", default=not DEBUG)
CSP_REPORT_ONLY = env.bool("CSP_REPORT_ONLY", default=True)
CONTENT_SECURITY_POLICY = build_content_security_policy(sentry_dsn=SENTRY_DSN)

LOG_LEVEL = env("LOG_LEVEL", default="DEBUG" if DEBUG else "INFO")
if _RUNNING_TESTS:
    LOG_LEVEL = "WARNING"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
        "request": {
            "format": "{levelname} {asctime} {name} request_id={request_id} {message}",
            "style": "{",
        },
    },
    "filters": {
        "request_id": {
            "()": "config.logging_filters.RequestIdFilter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "request_console": {
            "class": "logging.StreamHandler",
            "formatter": "request",
            "filters": ["request_id"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django.request": {
            "level": "ERROR",
            "handlers": ["request_console"],
            "propagate": False,
        },
        "celery": {"level": "INFO"},
        "integrations": {"level": "INFO"},
        "accounts": {"level": "INFO"},
    },
}
if _RUNNING_TESTS:
    LOGGING["root"]["level"] = "WARNING"
    LOGGING["loggers"].update(
        {
            "django.request": {
                "level": "CRITICAL",
                "handlers": ["request_console"],
                "propagate": False,
            },
            "urllib3": {"level": "WARNING", "propagate": False},
            "urllib3.connectionpool": {"level": "WARNING", "propagate": False},
            "PIL": {"level": "WARNING", "propagate": False},
            "rlp": {"level": "WARNING", "propagate": False},
            "celery": {"level": "WARNING"},
            "integrations": {"level": "WARNING"},
            "integrations.services": {"level": "CRITICAL", "propagate": False},
            "accounts": {"level": "WARNING"},
            "accounts.follow_services": {"level": "CRITICAL", "propagate": False},
        }
    )

validate_production_settings(
    debug=DEBUG,
    secret_key=SECRET_KEY,
    eas_offchain_signing_key=EAS_OFFCHAIN_SIGNING_KEY,
    email_verification_dev_show_link=EMAIL_VERIFICATION_DEV_SHOW_LINK,
    allowed_hosts=ALLOWED_HOSTS,
    admin_url_path=ADMIN_URL_PATH,
    environment=DJANGO_ENV,
    running_tests=_RUNNING_TESTS,
    use_s3_media=USE_S3_MEDIA,
    on_heroku=bool(os.environ.get("DYNO")),
    dyno=os.environ.get("DYNO", ""),
    enable_embedded_market_sync=ENABLE_EMBEDDED_MARKET_SYNC,
    embedded_market_sync_on_web=os.environ.get("EMBEDDED_MARKET_SYNC_ON_WEB", "").lower()
    in {"1", "true", "yes"},
    web_concurrency=env.int("WEB_CONCURRENCY", default=2),
    gunicorn_threads=env.int("GUNICORN_THREADS", default=4),
)

# Error monitoring (optional — no-op when SENTRY_DSN is unset)
SENTRY_ENVIRONMENT = env("SENTRY_ENVIRONMENT", default="production" if not DEBUG else "development")
SENTRY_TRACES_SAMPLE_RATE = env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.1)

from config.sentry_init import init_sentry  # noqa: E402

init_sentry()
