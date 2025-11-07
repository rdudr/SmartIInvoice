#!/bin/bash
# Celery Worker Startup Script for Unix/Linux/macOS
# This script starts a Celery worker for processing background tasks

echo "========================================"
echo "Smart iInvoice - Celery Worker Startup"
echo "========================================"
echo ""
echo "Make sure Redis is running before starting the worker!"
echo "You can start Redis with: redis-server"
echo ""

# Set environment variables if needed
# export DJANGO_SETTINGS_MODULE=smartinvoice.settings

# Check if production mode
read -p "Run in production mode? (y/n, default: n): " PRODUCTION

if [[ "$PRODUCTION" == "y" || "$PRODUCTION" == "Y" ]]; then
    echo ""
    echo "Starting Celery worker in PRODUCTION mode..."
    echo "Configuration:"
    echo "  - Concurrency: 4 workers"
    echo "  - Task time limit: 30 minutes"
    echo "  - Max retries: 3"
    echo "  - Max tasks per child: 1000"
    echo ""
    celery -A smartinvoice worker --config=celery_config_production --loglevel=info --concurrency=4 --max-tasks-per-child=1000
else
    echo ""
    echo "Starting Celery worker in DEVELOPMENT mode..."
    echo "Configuration:"
    echo "  - Concurrency: 2 workers"
    echo ""
    celery -A smartinvoice worker --loglevel=info --concurrency=2
fi

# For production with systemd, create a service file:
# sudo nano /etc/systemd/system/celery-smartinvoice.service
#
# [Unit]
# Description=Celery Worker for Smart iInvoice
# After=network.target redis.service
#
# [Service]
# Type=forking
# User=www-data
# Group=www-data
# WorkingDirectory=/path/to/smartinvoice
# ExecStart=/path/to/venv/bin/celery -A smartinvoice worker --config=celery_config_production --loglevel=info --concurrency=4 --detach
# Restart=always
#
# [Install]
# WantedBy=multi-user.target
