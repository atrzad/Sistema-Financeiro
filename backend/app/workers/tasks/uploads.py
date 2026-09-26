"""Tasks de upload: validação de comprovantes e recuperação de envios abandonados."""

import uuid
from typing import Any

from billiard.einfo import ExceptionInfo
from botocore.exceptions import BotoCoreError, ClientError, EndpointConnectionError
from celery import Task
from sqlalchemy.exc import OperationalError

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.lote_cache import get_lote_cache
from app.services.storage import comprovantes_storage
from app.services.validacao_service import (
    marcar_falha_validacao,
    recuperar_abandonados,
    validar_comprovante,
)
from app.workers.celery_app import celery_app
from app.workers.runtime import run_async

log = get_logger("worker.uploads")

TRANSITORIOS = (EndpointConnectionError, BotoCoreError, ClientError, OperationalError, OSError)


# O stub do Celery tipa Task como genérico, mas a classe real não aceita Task[...].
class _ValidacaoTask(Task):  # type: ignore[type-arg]
    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: ExceptionInfo,
    ) -> None:
        """Chamado quando não há mais retry: o usuário recebe uma resposta em vez de
        um "validando" eterno."""
        tenant_id, comprovante_id = args
        log.error("validacao_falhou", comprovante_id=comprovante_id, error=repr(exc))
        try:
            run_async(
                marcar_falha_validacao(
                    uuid.UUID(tenant_id), uuid.UUID(comprovante_id), get_lote_cache()
                )
            )
        except Exception as erro:  # banco fora: a rotina de manutenção encerra depois
            log.error("marcar_falha_indisponivel", comprovante_id=comprovante_id, error=repr(erro))


@celery_app.task(
    base=_ValidacaoTask,
    name="app.workers.tasks.uploads.validar_arquivo",
    autoretry_for=TRANSITORIOS,
    retry_backoff=5,
    retry_backoff_max=120,
    retry_jitter=True,
    max_retries=4,
    acks_late=True,
    # Validar um arquivo de até 10 MB leva segundos; o limite brando dá tempo de
    # registrar a falha antes de o processo ser encerrado.
    soft_time_limit=50,
    time_limit=60,
)
def validar_arquivo(tenant_id: str, comprovante_id: str) -> str:
    return run_async(
        validar_comprovante(
            uuid.UUID(tenant_id),
            uuid.UUID(comprovante_id),
            get_settings(),
            comprovantes_storage(),
            get_lote_cache(),
        )
    )


def enfileirar_validacao(tenant_id: uuid.UUID, comprovante_id: uuid.UUID) -> None:
    validar_arquivo.delay(str(tenant_id), str(comprovante_id))


@celery_app.task(name="app.workers.tasks.uploads.recuperar_uploads_abandonados")
def recuperar_uploads_abandonados() -> dict[str, int]:
    resultado = run_async(
        recuperar_abandonados(comprovantes_storage(), enfileirar_validacao, get_lote_cache())
    )
    if any(resultado.values()):
        log.info("uploads_abandonados", **resultado)
    return resultado
