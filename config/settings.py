import os
import sys
from pathlib import Path

import environ
import ssl

# ``manage.py test`` / pytest should not require a local Redis for Django cache.
_RUNNING_TESTS = "test" in sys.argv or "pytest" in sys.argv[0]

from celery.schedules import crontab

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, True),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)

environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = env("SECRET_KEY", default="django-insecure-dev-key-change-in-production")
DEBUG = env("DEBUG")
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
EAS_ATTESTER_ID = env("EAS_ATTESTER_ID", default="proofrep-platform-v1")
EAS_OFFCHAIN_SIGNING_KEY = env("EAS_OFFCHAIN_SIGNING_KEY", default=SECRET_KEY)
EAS_CHAIN_ID = env.int("EAS_CHAIN_ID", default=0)
EAS_VERIFYING_CONTRACT = env("EAS_VERIFYING_CONTRACT", default="")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "accounts",
    "markets",
    "predictions",
    "comments",
    "reputation",
    "integrations",
    "dashboard",
    "challenges",
    "pulse",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
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
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

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

# Pulse image uploads — local disk in dev; S3 in production (Heroku). Profile avatars are generated (DiceBear).
USE_S3_MEDIA = env.bool("USE_S3_MEDIA", default=bool(env("AWS_STORAGE_BUCKET_NAME", default="")))
if USE_S3_MEDIA:
    INSTALLED_APPS.append("storages")
    AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY")
    AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME")
    AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="us-east-1")
    AWS_S3_CUSTOM_DOMAIN = env(
        "AWS_S3_CUSTOM_DOMAIN",
        default=f"{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com",
    )
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}
    AWS_DEFAULT_ACL = "public-read"
    AWS_QUERYSTRING_AUTH = False
    AWS_S3_FILE_OVERWRITE = False
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
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/"

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

# Heroku Redis uses rediss:// — Celery/kombu need explicit SSL (same as Django cache).
if _redis_url.startswith("rediss://"):
    _redis_ssl = {"ssl_cert_reqs": ssl.CERT_NONE}
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
        redis_cache_options["ssl_cert_reqs"] = None
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
ENABLE_EMBEDDED_MARKET_SYNC = env.bool("ENABLE_EMBEDDED_MARKET_SYNC", default=False)
# 0 = import every available World Cup group-stage match from Polymarket.
WORLD_CUP_MATCH_SYNC_LIMIT = env.int("WORLD_CUP_MATCH_SYNC_LIMIT", default=0)
MARKET_SYNC_STALE_MINUTES = env.int("MARKET_SYNC_STALE_MINUTES", default=30)
MARKET_SYNC_STALE_BATCH_SIZE = env.int("MARKET_SYNC_STALE_BATCH_SIZE", default=100)
MARKET_TRANSLATION_ENABLED = env.bool("MARKET_TRANSLATION_ENABLED", default=False)
MARKET_TRANSLATION_CACHE_SECONDS = env.int("MARKET_TRANSLATION_CACHE_SECONDS", default=60 * 60 * 24 * 30)
MARKET_TRANSLATION_REQUEST_DELAY = env.float("MARKET_TRANSLATION_REQUEST_DELAY", default=0.35)
DEEPL_AUTH_KEY = env("DEEPL_AUTH_KEY", default="")
DEEPL_API_URL = env("DEEPL_API_URL", default="https://api-free.deepl.com/v2/translate")
CATEGORY_SYNC_FAILURE_COOLDOWN_SECONDS = env.int(
    "CATEGORY_SYNC_FAILURE_COOLDOWN_SECONDS",
    default=120,
)

REST_FRAMEWORK = {
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

# Reputation scoring defaults
REPUTATION_BASE_POINTS = 10
REPUTATION_BASE_PENALTY = 5
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

CELERY_BEAT_SCHEDULE = {
    "sync-all-category-markets": {
        "task": "integrations.tasks.sync_all_category_markets_task",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "refresh-stale-open-markets": {
        "task": "integrations.tasks.refresh_stale_open_markets_task",
        "schedule": crontab(minute=30, hour="*/6"),
    },
}
# Daily re-engagement digest (Substack-style summary).
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
