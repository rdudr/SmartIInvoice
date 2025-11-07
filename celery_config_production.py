"""
Production Celery Configuration for Smart iInvoice

This file contains production-specific Celery configuration.
It should be used when running Celery workers in production environments.

Usage:
    celery -A smartinvoice worker --config=celery_config_production -l info
"""

# Worker Configuration
worker_concurrency = 4  # Number of concurrent worker processes (adjust based on CPU cores)
worker_pool = 'prefork'  # Use prefork pool for better isolation
worker_max_memory_per_child = 200000  # 200MB per child process (restart after reaching limit)
worker_max_tasks_per_child = 1000  # Restart worker after 1000 tasks

# Task Configuration
task_acks_late = True  # Acknowledge tasks after execution
task_reject_on_worker_lost = True  # Reject tasks if worker crashes
task_track_started = True  # Track when tasks start

# Time Limits
task_time_limit = 1800  # 30 minutes hard limit
task_soft_time_limit = 1500  # 25 minutes soft limit

# Retry Configuration
task_default_retry_delay = 60  # 1 minute between retries
task_max_retries = 3  # Maximum 3 retry attempts

# Result Backend
result_expires = 3600  # Results expire after 1 hour
result_persistent = True  # Persist results to disk

# Prefetch Settings
worker_prefetch_multiplier = 1  # Fetch one task at a time for long-running tasks

# Rate Limiting
worker_disable_rate_limits = False  # Enable rate limiting

# Monitoring
worker_send_task_events = True  # Send task events for monitoring
task_send_sent_event = True  # Send event when task is sent

# Logging
worker_hijack_root_logger = False  # Don't hijack root logger
worker_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
worker_task_log_format = '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s'

# Queue Configuration
task_routes = {
    'invoice_processor.tasks.process_invoice_async': {
        'queue': 'invoices',
        'priority': 5,
    },
    'invoice_processor.tasks.process_batch_invoices': {
        'queue': 'invoices',
        'priority': 3,
    },
}

# Broker Configuration
broker_connection_retry_on_startup = True  # Retry connecting to broker on startup
broker_connection_retry = True  # Retry on connection loss
broker_connection_max_retries = 10  # Maximum retry attempts

# Security
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']  # Only accept JSON serialized content

# Timezone
timezone = 'UTC'
enable_utc = True
