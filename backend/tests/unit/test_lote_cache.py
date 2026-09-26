import uuid

import fakeredis
import pytest

from app.models import UploadBatch
from app.schemas.uploads import ItemStatus, StatusProcessamento
from app.services.lote_cache import TTL_S, LoteStatusCache

EMPRESA, DONO = uuid.uuid4(), uuid.uuid4()


def _lote(total: int) -> UploadBatch:
    return UploadBatch(
        id=uuid.uuid4(), tenant_id=EMPRESA, usuario_id=DONO, total_arquivos=total, tamanho_total=1
    )


def _item(nome: str, status: StatusProcessamento = "enviando") -> ItemStatus:
    return ItemStatus(
        comprovante_id=uuid.uuid4(),
        nome=nome,
        tamanho_bytes=100,
        mime_type="application/pdf",
        status=status,
        erro_msg=None,
        total_paginas=1,
        possivel_duplicado=False,
        tem_miniatura=False,
    )


def _campos(lote: UploadBatch, *itens: ItemStatus) -> dict[uuid.UUID, dict[str, str]]:
    return {lote.id: {f"item:{i.comprovante_id}": i.model_dump_json() for i in itens}}


@pytest.fixture
def server() -> fakeredis.FakeServer:
    return fakeredis.FakeServer()


@pytest.fixture
def cache(server: fakeredis.FakeServer) -> LoteStatusCache:
    return LoteStatusCache(
        fakeredis.FakeRedis(server=server, decode_responses=True),
        fakeredis.FakeAsyncRedis(server=server, decode_responses=True),
    )


async def test_le_o_lote_completo(cache: LoteStatusCache) -> None:
    lote, itens = _lote(2), [_item("a.pdf"), _item("b.pdf")]
    assert await cache.ler(lote.id, EMPRESA, DONO) is None

    await cache.preencher(lote, itens)

    lidos = await cache.ler(lote.id, EMPRESA, DONO)
    assert lidos is not None
    assert sorted(lidos, key=lambda i: i.nome) == itens
    assert await cache.ler(lote.id, EMPRESA, None) is not None  # admin: sem checar dono
    assert 0 < await cache.aio.ttl(f"batch:{lote.id}") <= TTL_S


async def test_so_o_dono_na_mesma_empresa_le_do_cache(cache: LoteStatusCache) -> None:
    lote = _lote(1)
    await cache.preencher(lote, [_item("a.pdf")])

    assert await cache.ler(lote.id, uuid.uuid4(), None) is None  # outra empresa
    assert await cache.ler(lote.id, EMPRESA, uuid.uuid4()) is None  # outro usuário


async def test_lote_incompleto_no_cache_vai_ao_banco(cache: LoteStatusCache) -> None:
    lote, a, b = _lote(2), _item("a.pdf"), _item("b.pdf", "validando")
    cache._gravar(_campos(lote, b))  # o worker gravou só um item; ninguém gravou o lote
    assert await cache.ler(lote.id, EMPRESA, DONO) is None

    await cache.preencher(lote, [a, b])
    assert await cache.ler(lote.id, EMPRESA, DONO) is not None


async def test_retrato_antigo_do_banco_nao_sobrescreve_estado_novo(cache: LoteStatusCache) -> None:
    lote, lido_do_banco = _lote(1), _item("a.pdf", "validando")
    # Entre a leitura do banco e o preenchimento do cache, o worker concluiu o item...
    concluido = lido_do_banco.model_copy(update={"status": "concluido"})
    cache._gravar(_campos(lote, concluido))
    # ...e o preenchimento com o retrato antigo chega depois.
    await cache.preencher(lote, [lido_do_banco])

    lidos = await cache.ler(lote.id, EMPRESA, DONO)
    assert [i.status for i in lidos or []] == ["concluido"]


async def test_conteudo_invalido_e_ignorado(cache: LoteStatusCache) -> None:
    lote = _lote(1)
    cache.sync.hset(f"batch:{lote.id}", mapping={"meta": "{quebrado", "item:x": "{}"})
    assert await cache.ler(lote.id, EMPRESA, DONO) is None

    await cache.aio.delete(f"batch:{lote.id}")
    await cache.preencher(lote, [_item("a.pdf")])
    cache.sync.hset(f"batch:{lote.id}", "item:y", "não é json")
    assert await cache.ler(lote.id, EMPRESA, DONO) is None


async def test_redis_fora_do_ar_nao_quebra_nada(
    cache: LoteStatusCache, server: fakeredis.FakeServer
) -> None:
    lote, item = _lote(1), _item("a.pdf")
    server.connected = False

    assert await cache.ler(lote.id, EMPRESA, DONO) is None
    await cache.preencher(lote, [item])
    cache._gravar(_campos(lote, item))
