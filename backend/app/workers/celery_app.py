"""Aplicação Celery e roteamento de filas (ver docs/arquitetura.md)."""

from celery import Celery
from kombu import Queue

from app.core.config import get_settings
from app.core.logging import configure_logging

QUEUES = ("validation", "ocr", "reports", "maintenance")

settings = get_settings()
configure_logging(settings.log_level, json=not settings.is_local)

celery_app = Celery(
    "financeiro",
    broker=str(settings.redis_url),
    backend=str(settings.redis_url),
    include=["app.workers.tasks.ping"],
)
celery_app.conf.update(
    task_default_queue="celery",
    task_queues=[Queue("celery"), *(Queue(q) for q in QUEUES)],
    task_routes={"app.workers.tasks.ping.*": {"queue": "maintenance"}},
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,  # task só sai da fila depois de concluída
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    # Logs da aplicação saem direto pelo structlog, sem o Celery reclassificá-los.
    worker_redirect_stdouts=False,
    timezone="America/Sao_Paulo",
    enable_utc=True,
)

# Alias esperado por `celery -A app.workers.celery_app`
app = celery_app
