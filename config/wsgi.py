import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

application = get_wsgi_application()

# Eagerly resolve URLconf during worker preload so gthread threads do not race
# on lazy imports (requests ↔ urllib.request) on the first concurrent requests.
from django.urls import get_resolver

get_resolver().url_patterns
