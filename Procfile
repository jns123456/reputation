web: gunicorn config.wsgi:application --worker-class gthread --workers ${WEB_CONCURRENCY:-2} --threads ${GUNICORN_THREADS:-4} --preload --max-requests ${GUNICORN_MAX_REQUESTS:-500} --max-requests-jitter ${GUNICORN_MAX_REQUESTS_JITTER:-50} --timeout ${GUNICORN_TIMEOUT:-30} --log-file -
worker: celery -A config worker -B --loglevel=info --concurrency=${CELERY_WORKER_CONCURRENCY:-1} --max-tasks-per-child=${CELERY_MAX_TASKS_PER_CHILD:-100}
beat: celery -A config beat --loglevel=info
release: python manage.py migrate --noinput
