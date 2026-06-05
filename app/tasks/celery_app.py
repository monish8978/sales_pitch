from celery import Celery
from app.config import settings

celery_app = Celery(
    "sales_pitch_tasks",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend
)

# Optional configuration overrides
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Make sure tasks are imported
    imports=["app.tasks.pitch_tasks"]
)
