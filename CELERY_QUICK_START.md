# Celery Quick Start Guide

Quick reference for running Celery with Smart iInvoice.

## Prerequisites

✅ Python dependencies installed: `pip install -r requirements.txt`
✅ Redis installed and accessible

## Quick Start (3 Steps)

### 1. Start Redis

**Windows:**
```cmd
start_redis.bat
```

**Unix/Linux/macOS:**
```bash
redis-server
```

**Verify Redis is running:**
```bash
redis-cli ping
# Should return: PONG
```

### 2. Start Celery Worker

**Windows:**
```cmd
start_celery_worker.bat
```

**Unix/Linux/macOS:**
```bash
chmod +x start_celery_worker.sh
./start_celery_worker.sh
```

**Or manually:**
```bash
# Windows
celery -A smartinvoice worker --loglevel=info --pool=solo --concurrency=2

# Unix/Linux/macOS
celery -A smartinvoice worker --loglevel=info --concurrency=2
```

### 3. Test the Setup

```bash
python manage.py test_celery
```

Expected output:
```
Testing Celery connection...
Make sure Redis and Celery worker are running!

Queuing test task...
Task ID: abc123...
Waiting for result (timeout: 10 seconds)...
✓ Success: Celery is working correctly!
✓ Celery is configured correctly!
```

## Common Commands

### Check Worker Status
```bash
celery -A smartinvoice inspect active
```

### List Registered Tasks
```bash
celery -A smartinvoice inspect registered
```

### Monitor Tasks (Real-time)
```bash
celery -A smartinvoice events
```

### Purge All Tasks
```bash
celery -A smartinvoice purge
```

## Troubleshooting

### Redis Connection Error
**Problem:** `Error 10061: No connection could be made`

**Solution:**
1. Start Redis: `redis-server`
2. Verify: `redis-cli ping`
3. Check `CELERY_BROKER_URL` in `.env`

### Tasks Not Executing
**Problem:** Tasks queued but not processing

**Solution:**
1. Check Celery worker is running
2. Check worker logs for errors
3. Verify tasks are registered: `celery -A smartinvoice inspect registered`

### Import Errors
**Problem:** `ImportError: cannot import name 'celery_app'`

**Solution:**
1. Make sure you're in the project root directory
2. Set Django settings: `export DJANGO_SETTINGS_MODULE=smartinvoice.settings`
3. Restart Celery worker

## Development Workflow

1. **Start Redis** (once, keep running)
   ```bash
   redis-server
   ```

2. **Start Celery Worker** (once, keep running)
   ```bash
   celery -A smartinvoice worker --loglevel=info --pool=solo
   ```

3. **Start Django Server** (in separate terminal)
   ```bash
   python manage.py runserver
   ```

4. **Develop and Test**
   - Make code changes
   - Test with: `python manage.py test_celery`
   - Restart Celery worker if you modify tasks.py

## Using Tasks in Code

```python
from invoice_processor.tasks import process_invoice_async

# Queue a task (non-blocking)
result = process_invoice_async.delay(invoice_id=123)

# Check if task is complete
if result.ready():
    print("Task completed!")
    print(result.get())
else:
    print("Task still processing...")

# Wait for result (blocking, with timeout)
try:
    result_data = result.get(timeout=30)
    print(f"Result: {result_data}")
except TimeoutError:
    print("Task took too long!")
```

## Production Notes

For production deployment:
- Use process manager (Supervisor, systemd)
- Increase concurrency: `--concurrency=4`
- Set up monitoring (Flower)
- Configure proper logging
- Use Redis persistence

See [CELERY_SETUP.md](CELERY_SETUP.md) for detailed production setup.

## Need Help?

- Full documentation: [CELERY_SETUP.md](CELERY_SETUP.md)
- Celery docs: https://docs.celeryproject.org/
- Redis docs: https://redis.io/documentation
