@echo off
REM Celery Worker Startup Script for Windows
REM This script starts a Celery worker for processing background tasks

echo ========================================
echo Smart iInvoice - Celery Worker Startup
echo ========================================
echo.
echo Make sure Redis is running before starting the worker!
echo You can start Redis with: redis-server
echo.

REM Set environment variables if needed
REM set DJANGO_SETTINGS_MODULE=smartinvoice.settings

REM Check if production mode
set /p PRODUCTION="Run in production mode? (y/n, default: n): "

if /i "%PRODUCTION%"=="y" (
    echo.
    echo Starting Celery worker in PRODUCTION mode...
    echo Configuration:
    echo   - Concurrency: 4 workers
    echo   - Task time limit: 30 minutes
    echo   - Max retries: 3
    echo   - Pool: solo (Windows compatible)
    echo.
    celery -A smartinvoice worker --config=celery_config_production --loglevel=info --pool=solo --concurrency=4
) else (
    echo.
    echo Starting Celery worker in DEVELOPMENT mode...
    echo Configuration:
    echo   - Concurrency: 2 workers
    echo   - Pool: solo (Windows compatible)
    echo.
    celery -A smartinvoice worker --loglevel=info --pool=solo --concurrency=2
)

REM Note: --pool=solo is used for Windows compatibility
REM For production on Windows, consider using eventlet or gevent:
REM pip install eventlet
REM celery -A smartinvoice worker --loglevel=info --pool=eventlet --concurrency=4

pause
