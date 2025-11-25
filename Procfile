web: gunicorn smartinvoice.wsgi --log-file -
worker: celery -A smartinvoice worker --loglevel=info --pool=solo --concurrency=2
