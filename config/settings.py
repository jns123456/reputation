import os
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, True),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)

environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = env("SECRET_KEY", default="django-insecure-dev-key-change-in-production")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

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
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTH_USER_MODEL = "accounts.User"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
if DEBUG:
    STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
else:
    STATICFILES_STORAGE = "whitenoise.storage.CompressedStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "dashboard:home"
LOGOUT_REDIRECT_URL = "dashboard:landing"

CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "reputation-cache",
    }
}

POLYMARKET_ECONOMY_CACHE_SECONDS = env.int("POLYMARKET_ECONOMY_CACHE_SECONDS", default=300)

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

POLYMARKET_API_URL = env(
    "POLYMARKET_API_URL",
    default="https://gamma-api.polymarket.com",
)

# Official Polymarket embed widget — https://embed.polymarket.com/
POLYMARKET_EMBED_BASE_URL = env(
    "POLYMARKET_EMBED_BASE_URL",
    default="https://embed.polymarket.com/market",
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
