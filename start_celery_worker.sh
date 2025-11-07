#!/bin/bash
# Celery Worker Startup Script for Unix/Linux/macOS
# This script starts a Celery worker for processing background tasks

echo "Starting Celery Worker for Smart iInvoice..."
echo ""
echo "Make sure Redis is running before starting the worker!"
echo "You can start Redis with: redis-server"
echo ""

# Set environment variables if needed
# export DJANGO_SETTINGS_MODULE=smartinvoice.settings

# Start Celery worker with appropriate settings
celery -A smartinvoice worker --loglevel=info --concurrency=2

# For production, you might want to use:
# celery -A smartinvoice worker --loglevel=info --concurrency=4 --max-tasks-per-child=1000
