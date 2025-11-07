@echo off
REM Celery Worker Startup Script for Windows
REM This script starts a Celery worker for processing background tasks

echo Starting Celery Worker for Smart iInvoice...
echo.
echo Make sure Redis is running before starting the worker!
echo You can start Redis with: redis-server
echo.

REM Set environment variables if needed
REM set DJANGO_SETTINGS_MODULE=smartinvoice.settings

REM Start Celery worker with appropriate settings
celery -A smartinvoice worker --loglevel=info --pool=solo --concurrency=2

REM Note: --pool=solo is used for Windows compatibility
REM For production on Windows, consider using eventlet or gevent:
REM pip install eventlet
REM celery -A smartinvoice worker --loglevel=info --pool=eventlet --concurrency=2

pause
