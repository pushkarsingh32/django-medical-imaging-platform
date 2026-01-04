"""
Celery configuration for Medical Imaging Platform.

This module configures Celery for asynchronous task processing.
"""
import os
from celery import Celery
from decouple import config

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Create Celery app
app = Celery('config')

# Load configuration from Django settings with 'CELERY_' prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks in all installed apps
app.autodiscover_tasks()

# Configure Celery to use Redis as broker and backend
app.conf.update(
    broker_url=f"redis://{config('REDIS_HOST', default='localhost')}:{config('REDIS_PORT', default='6379')}/{config('CELERY_BROKER_DB', default='1')}",
    result_backend=f"redis://{config('REDIS_HOST', default='localhost')}:{config('REDIS_PORT', default='6379')}/{config('CELERY_RESULT_DB', default='2')}",
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes max per task
    task_soft_time_limit=25 * 60,  # Soft limit at 25 minutes
    worker_prefetch_multiplier=1,  # Disable prefetching for long-running tasks
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks (prevent memory leaks)
)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task to test Celery is working"""
    print(f'Request: {self.request!r}')
