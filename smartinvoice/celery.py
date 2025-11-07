"""
Celery configuration for Smart iInvoice project.

This module sets up Celery for asynchronous task processing,
enabling background processing of invoices and other long-running operations.

Production Configuration:
- Task time limits and retries
- Result backend configuration
- Worker concurrency settings
- Task routing and priorities
- Monitoring and logging
"""

import os
from celery import Celery
from celery.signals import task_failure, task_success, worker_ready
import logging

logger = logging.getLogger(__name__)

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartinvoice.settings')

app = Celery('smartinvoice')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Production Configuration
app.conf.update(
    # Task execution settings
    task_acks_late=True,  # Acknowledge tasks after execution, not before
    task_reject_on_worker_lost=True,  # Reject tasks if worker crashes
    task_track_started=True,  # Track when tasks start
    
    # Time limits (in seconds)
    task_time_limit=1800,  # 30 minutes hard limit
    task_soft_time_limit=1500,  # 25 minutes soft limit
    
    # Retry settings
    task_default_retry_delay=60,  # 1 minute between retries
    task_max_retries=3,  # Maximum 3 retry attempts
    
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    result_persistent=True,  # Persist results to disk
    
    # Worker settings
    worker_prefetch_multiplier=1,  # Fetch one task at a time for long-running tasks
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks to prevent memory leaks
    worker_disable_rate_limits=False,  # Enable rate limiting
    
    # Task routing
    task_routes={
        'invoice_processor.tasks.process_invoice_async': {
            'queue': 'invoices',
            'priority': 5,
        },
        'invoice_processor.tasks.process_batch_invoices': {
            'queue': 'invoices',
            'priority': 3,
        },
    },
    
    # Monitoring
    worker_send_task_events=True,  # Send task events for monitoring
    task_send_sent_event=True,  # Send event when task is sent
    
    # Serialization
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='UTC',
    enable_utc=True,
)


# Signal handlers for monitoring and logging
@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, einfo=None, **kw):
    """Log task failures for monitoring"""
    logger.error(
        f'Task {sender.name} [{task_id}] failed: {exception}',
        exc_info=einfo,
        extra={
            'task_name': sender.name,
            'task_id': task_id,
            'args': args,
            'kwargs': kwargs,
        }
    )


@task_success.connect
def task_success_handler(sender=None, result=None, **kwargs):
    """Log successful task completion"""
    logger.info(
        f'Task {sender.name} completed successfully',
        extra={
            'task_name': sender.name,
            'result': result,
        }
    )


@worker_ready.connect
def worker_ready_handler(sender=None, **kwargs):
    """Log when worker is ready"""
    logger.info(f'Celery worker ready: {sender.hostname}')


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    logger.info(f'Debug task executed: {self.request!r}')
    print(f'Request: {self.request!r}')
