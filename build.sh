#!/usr/bin/env bash
# exit on error
set -o errexit

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install gunicorn for production
pip install gunicorn whitenoise

# Collect static files
python manage.py collectstatic --no-input

# Run migrations
python manage.py migrate

# Create data directory if it doesn't exist
mkdir -p data

# Load HSN data if not already loaded
python manage.py load_hsn_data --force || echo "HSN data already loaded or files not found"
