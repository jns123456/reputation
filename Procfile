web: gunicorn config.wsgi:application --log-file -
release: python manage.py migrate --noinput && python manage.py sync_markets --categories --limit 48
