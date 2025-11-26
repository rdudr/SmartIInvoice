#!/bin/sh

# Exit on error
set -e

# Wait for database if DATABASE_URL is set (optional check)
# if [ -n "$DATABASE_URL" ]; then
#     echo "Waiting for database..."
#     # logic to wait for db
# fi

echo "Applying database migrations..."
python manage.py migrate

echo "Collecting static files..."
python manage.py collectstatic --no-input

echo "Loading HSN data..."
# Create data directory if it doesn't exist (redundant with Dockerfile but safe)
mkdir -p data
python manage.py load_hsn_data --force || echo "HSN data loading failed or skipped"

echo "Starting Gunicorn..."
exec gunicorn smartinvoice.wsgi:application --bind 0.0.0.0:8000 --workers 3 --log-file -
