web: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --log-level info
worker: celery -A config worker -l info -c 2 --max-tasks-per-child 50