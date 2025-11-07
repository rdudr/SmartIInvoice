"""
Django management command to test Celery setup.

Usage:
    python manage.py test_celery
"""

from django.core.management.base import BaseCommand
from invoice_processor.tasks import test_celery_connection


class Command(BaseCommand):
    help = 'Test Celery connection and task execution'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Testing Celery connection...'))
        self.stdout.write('Make sure Redis and Celery worker are running!')
        self.stdout.write('')
        
        try:
            # Queue the test task
            self.stdout.write('Queuing test task...')
            result = test_celery_connection.delay()
            
            self.stdout.write(f'Task ID: {result.id}')
            self.stdout.write('Waiting for result (timeout: 10 seconds)...')
            
            # Wait for result with timeout
            task_result = result.get(timeout=10)
            
            self.stdout.write(self.style.SUCCESS(f'✓ Success: {task_result}'))
            self.stdout.write(self.style.SUCCESS('✓ Celery is configured correctly!'))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error: {str(e)}'))
            self.stdout.write(self.style.ERROR('✗ Celery test failed!'))
            self.stdout.write('')
            self.stdout.write('Troubleshooting:')
            self.stdout.write('1. Make sure Redis is running: redis-cli ping')
            self.stdout.write('2. Make sure Celery worker is running: celery -A smartinvoice worker')
            self.stdout.write('3. Check CELERY_BROKER_URL in settings')
            return
