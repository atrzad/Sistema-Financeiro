"""Aplicação Celery e roteamento de filas (ver docs/arquitetura.md)."""

from typing import Any

from celery import Celery
from celery.signals import worker_process_init
from kombu import Queue

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import use_null_pool

QUEUES = ("validation", "ocr", "reports", "maintenance")

settings = get_settings()
configure_logging(settings.log_level, json=not settings.is_local)

celery_app = Celery(
    "financeiro",
    broker=str(settings.redis_url),
    backend=str(settings.redis_url),
    include=["app.workers.tasks.ping", "app.workers.tasks.uploads"],
)
celery_app.conf.update(
    task_default_queue="celery",
    task_queues=[Queue("celery"), *(Queue(q) for q in QUEUES)],
    task_routes={
        "app.workers.tasks.ping.*": {"queue": "maintenance"},
        "app.workers.tasks.uploads.validar_arquivo": {"queue": "validation"},
        "app.workers.tasks.uploads.recuperar_uploads_abandonados": {"queue": "maintenance"},
    },
    beat_schedule={
        "recuperar-uploads-abandonados": {
            "task": "app.workers.tasks.uploads.recuperar_uploads_abandonados",
            "schedule": 10 * 60,
        },
    },
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


@worker_process_init.connect
def _ao_iniciar_processo(**_: Any) -> None:
    use_null_pool()
