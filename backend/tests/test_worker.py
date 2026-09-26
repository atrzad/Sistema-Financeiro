import uuid

import pytest

from app.workers.celery_app import QUEUES, celery_app
from app.workers.tasks import uploads
from app.workers.tasks.ping import ping
from app.workers.tasks.uploads import validar_arquivo


def test_filas_declaradas() -> None:
    nomes = {q.name for q in celery_app.conf.task_queues}
    assert nomes == {"celery", *QUEUES}
    assert set(QUEUES) == {"validation", "ocr", "reports", "maintenance"}


def test_ping_roteado_para_manutencao() -> None:
    rota = celery_app.amqp.router.route({}, ping.name)
    assert rota["queue"].name == "maintenance"


def test_ping_executa() -> None:
    assert ping.apply(args=("teste",)).get() == "pong (teste)"


def test_validacao_roda_na_fila_validation_com_limite_de_tempo() -> None:
    rota = celery_app.amqp.router.route({}, validar_arquivo.name)
    assert rota["queue"].name == "validation"
    assert (validar_arquivo.soft_time_limit, validar_arquivo.time_limit) == (50, 60)


def test_falha_definitiva_da_validacao_encerra_o_comprovante(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sem mais retry, o comprovante não pode ficar "validando" para sempre."""
    chamadas: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def marcar(tenant_id: uuid.UUID, comp_id: uuid.UUID, _cache: object) -> None:
        chamadas.append((tenant_id, comp_id))

    monkeypatch.setattr(uploads, "marcar_falha_validacao", marcar)
    monkeypatch.setattr(uploads, "get_lote_cache", lambda: None)
    tenant_id, comp_id = uuid.uuid4(), uuid.uuid4()

    validar_arquivo.on_failure(
        RuntimeError("storage fora"),
        "task-1",
        (str(tenant_id), str(comp_id)),
        {},
        None,  # type: ignore[arg-type]
    )

    assert chamadas == [(tenant_id, comp_id)]
