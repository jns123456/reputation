import os
from pathlib import Path

import environ
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
KALSHI_ENABLED = env.bool("KALSHI_ENABLED", default=False)
DEV_FAST_MODE = env.bool("DEV_FAST_MODE", default=False)
NAV_BADGE_CACHE_SECONDS = env.int("NAV_BADGE_CACHE_SECONDS", default=60)
LEADERBOARD_CACHE_SECONDS = env.int("LEADERBOARD_CACHE_SECONDS", default=120)
WORLD_CUP_MATCHES_PER_PAGE = env.int("WORLD_CUP_MATCHES_PER_PAGE", default=24)

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
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
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
                "challenges.context_processors.challenge_context",
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

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
if DEBUG:
    STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
else:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
PULSE_MAX_IMAGE_BYTES = env.int("PULSE_MAX_IMAGE_BYTES", default=5 * 1024 * 1024)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "dashboard:landing"

CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_BROKER_CONNECTION_TIMEOUT = env.float("CELERY_BROKER_CONNECTION_TIMEOUT", default=0.5)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = False
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

if env("REDIS_URL", default=""):
    redis_url = env("REDIS_URL")
    redis_cache_options = {}
    if redis_url.startswith("rediss://"):
        redis_cache_options["ssl_cert_reqs"] = None
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
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

POLYMARKET_ECONOMY_CACHE_SECONDS = env.int("POLYMARKET_ECONOMY_CACHE_SECONDS", default=300)
MARKET_SYNC_CACHE_SECONDS = env.int("MARKET_SYNC_CACHE_SECONDS", default=POLYMARKET_ECONOMY_CACHE_SECONDS)
MARKET_SYNC_CATEGORY_LIMIT = env.int("MARKET_SYNC_CATEGORY_LIMIT", default=100)
MARKET_LIST_SORTED_LIMIT = env.int("MARKET_LIST_SORTED_LIMIT", default=200)
POLYMARKET_TOP_VOLUME_MIN_SHARE = env.float("POLYMARKET_TOP_VOLUME_MIN_SHARE", default=0.5)
POLYMARKET_TOP_VOLUME_MAX_MARKETS = env.int("POLYMARKET_TOP_VOLUME_MAX_MARKETS", default=500)
POLYMARKET_TOP_VOLUME_MAX_EVENT_PAGES = env.int("POLYMARKET_TOP_VOLUME_MAX_EVENT_PAGES", default=15)
MARKET_FULL_SYNC_INTERVAL_HOURS = env.int("MARKET_FULL_SYNC_INTERVAL_HOURS", default=6)
ENABLE_EMBEDDED_MARKET_SYNC = env.bool("ENABLE_EMBEDDED_MARKET_SYNC", default=False)
# 0 = import every available World Cup group-stage match from Polymarket.
WORLD_CUP_MATCH_SYNC_LIMIT = env.int("WORLD_CUP_MATCH_SYNC_LIMIT", default=0)
MARKET_SYNC_STALE_MINUTES = env.int("MARKET_SYNC_STALE_MINUTES", default=30)
MARKET_SYNC_STALE_BATCH_SIZE = env.int("MARKET_SYNC_STALE_BATCH_SIZE", default=100)
KALSHI_SYNC_OPEN_LIMIT = env.int("KALSHI_SYNC_OPEN_LIMIT", default=200)
KALSHI_SYNC_CATEGORY_LIMIT = env.int("KALSHI_SYNC_CATEGORY_LIMIT", default=12)
KALSHI_SYNC_CATEGORY_SERIES_LIMIT = env.int("KALSHI_SYNC_CATEGORY_SERIES_LIMIT", default=2)
KALSHI_SYNC_CACHE_SECONDS = env.int("KALSHI_SYNC_CACHE_SECONDS", default=900)
KALSHI_API_MIN_INTERVAL_MS = env.int("KALSHI_API_MIN_INTERVAL_MS", default=300)
KALSHI_API_MAX_RETRIES = env.int("KALSHI_API_MAX_RETRIES", default=3)
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

KALSHI_API_URL = env(
    "KALSHI_API_URL",
    default="https://external-api.kalshi.com/trade-api/v2",
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
if KALSHI_ENABLED:
    CELERY_BEAT_SCHEDULE["import-kalshi-open-markets"] = {
        "task": "integrations.tasks.import_kalshi_open_markets_task",
        "schedule": crontab(minute="5,35"),
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
KALSHI_EMBED_HEIGHT = env.int("KALSHI_EMBED_HEIGHT", default=POLYMARKET_EMBED_HEIGHT)
