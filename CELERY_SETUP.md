# Celery and Redis Setup Guide

This guide explains how to set up and run asynchronous task processing for Smart iInvoice using Celery and Redis.

## Prerequisites

### 1. Install Redis

**Windows:**
- Download Redis from: https://github.com/microsoftarchive/redis/releases
- Or use WSL (Windows Subsystem for Linux) and install Redis there
- Or use Docker: `docker run -d -p 6379:6379 redis:latest`

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install redis-server
```

**macOS:**
```bash
brew install redis
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- `celery==5.3.4` - Distributed task queue
- `redis==5.0.1` - Python Redis client

## Configuration

### Environment Variables

You can customize Celery configuration using environment variables in your `.env` file:

```env
# Celery Configuration
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### Django Settings

Celery configuration is already set up in `smartinvoice/settings.py` with sensible defaults:

- **Task time limits**: 30 minutes hard limit, 25 minutes soft limit
- **Task retries**: Maximum 3 retries with exponential backoff
- **Worker settings**: Prefetch multiplier of 1 for better task distribution
- **Result expiration**: 1 hour

## Running the System

### Step 1: Start Redis Server

**Windows:**
```cmd
start_redis.bat
```

**Unix/Linux/macOS:**
```bash
chmod +x start_redis.sh
./start_redis.sh
```

Or simply:
```bash
redis-server
```

Verify Redis is running:
```bash
redis-cli ping
# Should return: PONG
```

### Step 2: Start Celery Worker

**Windows:**
```cmd
start_celery_worker.bat
```

**Unix/Linux/macOS:**
```bash
chmod +x start_celery_worker.sh
./start_celery_worker.sh
```

Or manually:
```bash
# Development
celery -A smartinvoice worker --loglevel=info --concurrency=2

# Windows (use solo pool)
celery -A smartinvoice worker --loglevel=info --pool=solo --concurrency=2

# Production (Unix/Linux)
celery -A smartinvoice worker --loglevel=info --concurrency=4 --max-tasks-per-child=1000
```

### Step 3: Start Django Development Server

In a separate terminal:
```bash
python manage.py runserver
```

## Testing the Setup

### Test Celery Connection

You can test if Celery is working correctly using Django shell:

```python
python manage.py shell

>>> from invoice_processor.tasks import test_celery_connection
>>> result = test_celery_connection.delay()
>>> result.get(timeout=10)
'Celery is working correctly!'
```

### Monitor Tasks

You can monitor Celery tasks in real-time:

```bash
# Monitor active tasks
celery -A smartinvoice inspect active

# Monitor registered tasks
celery -A smartinvoice inspect registered

# Monitor worker stats
celery -A smartinvoice inspect stats
```

## Task Structure

### Available Tasks

1. **process_invoice_async** - Main task for processing invoices asynchronously
   - Handles AI extraction, compliance checks, GST verification, and health scoring
   - Supports batch processing with progress tracking
   - Automatic retry on failure (max 3 attempts)

2. **test_celery_connection** - Simple test task to verify Celery setup

3. **cleanup_old_results** - Periodic task for database maintenance

### Using Tasks in Code

```python
from invoice_processor.tasks import process_invoice_async

# Queue a task
result = process_invoice_async.delay(invoice_id=123, batch_id='uuid-here')

# Check task status
if result.ready():
    print(result.get())
else:
    print("Task is still processing...")
```

## Production Deployment

### Using Supervisor (Linux)

Create `/etc/supervisor/conf.d/smartinvoice-celery.conf`:

```ini
[program:smartinvoice-celery]
command=/path/to/venv/bin/celery -A smartinvoice worker --loglevel=info --concurrency=4
directory=/path/to/smartinvoice
user=www-data
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/celery/smartinvoice-worker.log
```

### Using systemd (Linux)

Create `/etc/systemd/system/smartinvoice-celery.service`:

```ini
[Unit]
Description=Smart iInvoice Celery Worker
After=network.target redis.service

[Service]
Type=forking
User=www-data
Group=www-data
WorkingDirectory=/path/to/smartinvoice
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/celery -A smartinvoice worker --loglevel=info --concurrency=4 --detach
ExecStop=/path/to/venv/bin/celery -A smartinvoice control shutdown
Restart=always

[Install]
WantedBy=multi-user.target
```

### Using Docker

```dockerfile
# Celery Worker Container
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["celery", "-A", "smartinvoice", "worker", "--loglevel=info", "--concurrency=4"]
```

## Troubleshooting

### Redis Connection Error

**Error:** `Error 10061: No connection could be made because the target machine actively refused it`

**Solution:** Make sure Redis server is running:
```bash
redis-cli ping
```

### Celery Worker Not Starting

**Error:** `ImportError: cannot import name 'celery_app'`

**Solution:** Make sure you're in the project root directory and Django settings are correct:
```bash
export DJANGO_SETTINGS_MODULE=smartinvoice.settings
```

### Tasks Not Executing

**Check:**
1. Redis is running: `redis-cli ping`
2. Celery worker is running and connected
3. Check worker logs for errors
4. Verify task is registered: `celery -A smartinvoice inspect registered`

### Windows-Specific Issues

On Windows, Celery may have issues with the default pool. Use `--pool=solo` or install eventlet:

```bash
pip install eventlet
celery -A smartinvoice worker --loglevel=info --pool=eventlet --concurrency=2
```

## Monitoring and Logging

### Celery Logs

Worker logs are output to console by default. For production, redirect to files:

```bash
celery -A smartinvoice worker --loglevel=info --logfile=/var/log/celery/worker.log
```

### Django Logs

Task execution is logged through Django's logging system. Check:
- `logs/smartinvoice.log` - General application logs
- `logs/errors.log` - Error logs

### Flower (Web-based Monitoring)

Install Flower for a web-based monitoring interface:

```bash
pip install flower
celery -A smartinvoice flower
```

Access at: http://localhost:5555

## Next Steps

After setting up Celery and Redis:

1. Implement bulk upload functionality (Task 8 in implementation plan)
2. Integrate async processing with invoice pipeline
3. Add progress tracking for batch operations
4. Implement periodic tasks for cache refresh and cleanup

## References

- [Celery Documentation](https://docs.celeryproject.org/)
- [Redis Documentation](https://redis.io/documentation)
- [Django Celery Integration](https://docs.celeryproject.org/en/stable/django/first-steps-with-django.html)
