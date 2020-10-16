import os
import celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'as207960_support.settings')

app = celery.Celery('as207960_support')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
