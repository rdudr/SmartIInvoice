#!/usr/bin/env python
"""
Verification script for Celery and Redis setup.

This script checks if all components of the asynchronous processing
infrastructure are properly configured and working.

Usage:
    python verify_celery_setup.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smartinvoice.settings')
django.setup()

from django.conf import settings
import redis


def print_header(text):
    """Print a formatted header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)


def print_success(text):
    """Print success message."""
    print(f"✓ {text}")


def print_error(text):
    """Print error message."""
    print(f"✗ {text}")


def print_warning(text):
    """Print warning message."""
    print(f"⚠ {text}")


def check_dependencies():
    """Check if required Python packages are installed."""
    print_header("Checking Dependencies")
    
    try:
        import celery
        print_success(f"Celery installed: {celery.__version__}")
    except ImportError:
        print_error("Celery not installed. Run: pip install celery==5.3.4")
        return False
    
    try:
        import redis
        print_success(f"Redis client installed: {redis.__version__}")
    except ImportError:
        print_error("Redis client not installed. Run: pip install redis==5.0.1")
        return False
    
    return True


def check_redis_connection():
    """Check if Redis server is running and accessible."""
    print_header("Checking Redis Connection")
    
    broker_url = getattr(settings, 'CELERY_BROKER_URL', 'redis://localhost:6379/0')
    print(f"Broker URL: {broker_url}")
    
    try:
        # Parse Redis URL
        if broker_url.startswith('redis://'):
            parts = broker_url.replace('redis://', '').split('/')
            host_port = parts[0].split(':')
            host = host_port[0] if host_port else 'localhost'
            port = int(host_port[1]) if len(host_port) > 1 else 6379
            db = int(parts[1]) if len(parts) > 1 else 0
        else:
            host, port, db = 'localhost', 6379, 0
        
        # Try to connect
        r = redis.Redis(host=host, port=port, db=db, socket_connect_timeout=5)
        r.ping()
        print_success(f"Redis server is running at {host}:{port}")
        
        # Check Redis info
        info = r.info()
        print(f"  Redis version: {info.get('redis_version', 'unknown')}")
        print(f"  Connected clients: {info.get('connected_clients', 'unknown')}")
        
        return True
        
    except redis.ConnectionError:
        print_error(f"Cannot connect to Redis at {host}:{port}")
        print("  Make sure Redis is running:")
        print("    - Windows: start_redis.bat")
        print("    - Unix/Linux/macOS: redis-server")
        return False
    except Exception as e:
        print_error(f"Redis connection error: {str(e)}")
        return False


def check_celery_config():
    """Check Celery configuration in Django settings."""
    print_header("Checking Celery Configuration")
    
    required_settings = [
        'CELERY_BROKER_URL',
        'CELERY_RESULT_BACKEND',
        'CELERY_ACCEPT_CONTENT',
        'CELERY_TASK_SERIALIZER',
    ]
    
    all_present = True
    for setting in required_settings:
        if hasattr(settings, setting):
            value = getattr(settings, setting)
            print_success(f"{setting}: {value}")
        else:
            print_error(f"{setting} not configured")
            all_present = False
    
    return all_present


def check_celery_app():
    """Check if Celery app is properly initialized."""
    print_header("Checking Celery App")
    
    try:
        from smartinvoice import celery_app
        print_success(f"Celery app loaded: {celery_app.main}")
        
        # Load tasks
        celery_app.loader.import_default_modules()
        
        # Check registered tasks
        app_tasks = [task for task in celery_app.tasks.keys() 
                     if 'invoice_processor' in task or 'smartinvoice' in task]
        
        if app_tasks:
            print_success(f"Found {len(app_tasks)} registered tasks:")
            for task in sorted(app_tasks):
                print(f"    - {task}")
            return True
        else:
            print_warning("No application tasks registered")
            return False
            
    except Exception as e:
        print_error(f"Error loading Celery app: {str(e)}")
        return False


def check_celery_worker():
    """Check if Celery worker is running."""
    print_header("Checking Celery Worker")
    
    try:
        from smartinvoice import celery_app
        
        # Try to inspect active workers
        inspect = celery_app.control.inspect(timeout=5)
        stats = inspect.stats()
        
        if stats:
            print_success(f"Found {len(stats)} active worker(s):")
            for worker_name, worker_stats in stats.items():
                print(f"    - {worker_name}")
                print(f"      Pool: {worker_stats.get('pool', {}).get('implementation', 'unknown')}")
                print(f"      Max concurrency: {worker_stats.get('pool', {}).get('max-concurrency', 'unknown')}")
            return True
        else:
            print_warning("No active Celery workers found")
            print("  Start a worker with:")
            print("    - Windows: start_celery_worker.bat")
            print("    - Unix/Linux/macOS: ./start_celery_worker.sh")
            print("    - Manual: celery -A smartinvoice worker --loglevel=info --pool=solo")
            return False
            
    except Exception as e:
        print_error(f"Cannot connect to Celery workers: {str(e)}")
        print("  Make sure a Celery worker is running")
        return False


def run_test_task():
    """Try to run a test task."""
    print_header("Running Test Task")
    
    try:
        from invoice_processor.tasks import test_celery_connection
        
        print("Queuing test task...")
        result = test_celery_connection.delay()
        print(f"Task ID: {result.id}")
        
        print("Waiting for result (timeout: 10 seconds)...")
        task_result = result.get(timeout=10)
        
        print_success(f"Task completed: {task_result}")
        return True
        
    except Exception as e:
        print_error(f"Test task failed: {str(e)}")
        print("  Make sure both Redis and Celery worker are running")
        return False


def main():
    """Run all verification checks."""
    print("\n" + "=" * 60)
    print("  Smart iInvoice - Celery Setup Verification")
    print("=" * 60)
    
    results = {
        'Dependencies': check_dependencies(),
        'Redis Connection': check_redis_connection(),
        'Celery Configuration': check_celery_config(),
        'Celery App': check_celery_app(),
        'Celery Worker': check_celery_worker(),
    }
    
    # Only run test task if all previous checks passed
    if all(results.values()):
        results['Test Task'] = run_test_task()
    
    # Print summary
    print_header("Verification Summary")
    
    for check, passed in results.items():
        if passed:
            print_success(f"{check}: PASSED")
        else:
            print_error(f"{check}: FAILED")
    
    # Overall result
    print("\n" + "=" * 60)
    if all(results.values()):
        print_success("All checks passed! Celery is ready to use.")
        print("\nYou can now:")
        print("  1. Start processing invoices asynchronously")
        print("  2. Implement bulk upload features")
        print("  3. Use background tasks in your application")
    else:
        print_error("Some checks failed. Please fix the issues above.")
        print("\nFor help, see:")
        print("  - CELERY_SETUP.md (detailed setup guide)")
        print("  - CELERY_QUICK_START.md (quick reference)")
    print("=" * 60 + "\n")
    
    # Exit with appropriate code
    sys.exit(0 if all(results.values()) else 1)


if __name__ == '__main__':
    main()
