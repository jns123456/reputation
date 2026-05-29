web: gunicorn config.wsgi:application --worker-class gthread --workers ${WEB_CONCURRENCY:-2} --threads ${GUNICORN_THREADS:-4} --preload --max-requests ${GUNICORN_MAX_REQUESTS:-500} --max-requests-jitter ${GUNICORN_MAX_REQUESTS_JITTER:-50} --timeout ${GUNICORN_TIMEOUT:-30} --log-file -
worker: celery -A config worker -B --loglevel=info --concurrency=2
release: python manage.py migrate --noinput && python manage.py sync_markets --categories --limit 48
