web: gunicorn config.wsgi:application --log-file -
worker: celery -A config worker -B --loglevel=info --concurrency=2
release: python manage.py migrate --noinput && python manage.py sync_markets --categories --limit 48
