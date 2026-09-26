import io
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from botocore.exceptions import ClientError
from fakeredis import FakeAsyncRedis, FakeServer
from fastapi import FastAPI
from PIL import Image
from sqlalchemy import select, update

from app.api.v1.uploads import get_enfileirar
from app.core.config import get_settings
from app.db.tenant import tenant_session
from app.models import Comprovante
from app.services import validacao_service
from app.services.lote_cache import LoteStatusCache
from app.services.storage import comprovantes_storage, get_s3_client
from app.services.validacao_service import (
    FALHA_VALIDACAO,
    marcar_falha_validacao,
    recuperar_abandonados,
    validar_comprovante,
)
from tests import arquivos as A
from tests.conftest import DemoTenant, bearer, login

BATCH = "/api/v1/uploads/batch"


@pytest.fixture
def fila(app: FastAPI, storage_bucket: str) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """Captura o que seria enfileirado; o teste roda a validação quando quiser."""
    enfileirados: list[tuple[uuid.UUID, uuid.UUID]] = []
    app.dependency_overrides[get_enfileirar] = lambda: lambda t, c: enfileirados.append((t, c))
    return enfileirados


async def _h(api: httpx.AsyncClient, t: DemoTenant, who: str = "colaborador") -> dict[str, str]:
    return bearer(await login(api, t.slug, f"{who}@{t.slug}.com.br"))


def _declarar(*arquivos: tuple[str, bytes]) -> dict[str, Any]:
    return {"arquivos": [{"nome": n, "tamanho_bytes": len(d)} for n, d in arquivos]}


async def _put(url: str, data: bytes, headers: dict[str, str]) -> httpx.Response:
    """PUT direto no storage, como o navegador faz (a API não vê o arquivo)."""
    async with httpx.AsyncClient() as s3:
        return await s3.put(url, content=data, headers=headers)


async def _get(url: str) -> httpx.Response:
    async with httpx.AsyncClient() as s3:
        return await s3.get(url)


async def _enviar(
    api: httpx.AsyncClient, h: dict[str, str], *arquivos: tuple[str, bytes]
) -> dict[str, Any]:
    """Fluxo do navegador: declara o lote, faz PUT de cada arquivo e confirma."""
    lote: dict[str, Any] = (await api.post(BATCH, json=_declarar(*arquivos), headers=h)).json()
    for item, (_, data) in zip(lote["itens"], arquivos, strict=True):
        put = await _put(item["upload_url"], data, item["headers"])
        assert put.status_code == 200, put.text
        r = await api.post(f"/api/v1/uploads/{item['comprovante_id']}/complete", headers=h)
        assert r.status_code == 202
    return lote


Processar = Callable[[list[tuple[uuid.UUID, uuid.UUID]]], Awaitable[None]]


@pytest.fixture
def processar(lote_cache: LoteStatusCache) -> Processar:
    """Simula o worker processando tudo o que foi enfileirado."""

    async def _processar(fila: list[tuple[uuid.UUID, uuid.UUID]]) -> None:
        while fila:
            tenant_id, comp_id = fila.pop(0)
            await validar_comprovante(
                tenant_id, comp_id, get_settings(), comprovantes_storage(), lote_cache
            )

    return _processar


async def _status(api: httpx.AsyncClient, h: dict[str, str], batch_id: str) -> dict[str, Any]:
    r = await api.get(f"{BATCH}/{batch_id}/status", headers=h)
    assert r.status_code == 200
    body: dict[str, Any] = r.json()
    return body


# --- Contrato ---------------------------------------------------------------------


def test_nenhuma_rota_de_upload_recebe_o_arquivo(app: FastAPI) -> None:
    """DoD: o arquivo vai do navegador direto ao storage — a API só recebe JSON."""
    rotas = {
        caminho: ops
        for caminho, ops in app.openapi()["paths"].items()
        if caminho.startswith(("/api/v1/uploads", "/api/v1/comprovantes"))
    }
    assert len(rotas) == 6
    for caminho, ops in rotas.items():
        for metodo, op in ops.items():
            tipos = set(op.get("requestBody", {}).get("content", {}))
            assert tipos <= {"application/json"}, (metodo, caminho, tipos)


# --- Declaração do lote -----------------------------------------------------------


async def test_cria_lote_com_url_por_arquivo(
    api: httpx.AsyncClient, acme: DemoTenant, fila: list[Any]
) -> None:
    r = await api.post(
        BATCH,
        json=_declarar(("C:\\Users\\ana\\boleto luz.pdf", b"x" * 100)),
        headers=await _h(api, acme),
    )
    assert r.status_code == 201
    item = r.json()["itens"][0]
    assert item["nome"] == "boleto luz.pdf"  # sem o caminho do computador do usuário
    assert item["headers"] == {"Content-Type": "application/pdf"}
    caminho = urlparse(item["upload_url"]).path
    assert caminho.startswith(f"/comprovantes-test/{acme.id}/")
    assert caminho.endswith(f"{item['comprovante_id']}.pdf")  # UUID, nunca o nome do cliente
    assert "boleto" not in caminho


@pytest.mark.parametrize(
    ("arquivos", "trecho"),
    [
        ([("a.pdf", 100)] * 11, "no máximo 10 arquivos"),
        ([("grande.pdf", 10 * 1024 * 1024 + 1)], "Há arquivos"),
        ([("programa.exe", 100), ("ok.pdf", 100)], "Há arquivos"),
        ([("a.pdf", 9 * 1024 * 1024)] * 7, "passa de 60 MB"),
    ],
)
async def test_recusa_lote_invalido_antes_de_qualquer_envio(
    api: httpx.AsyncClient,
    acme: DemoTenant,
    fila: list[Any],
    arquivos: list[tuple[str, int]],
    trecho: str,
) -> None:
    body = {"arquivos": [{"nome": n, "tamanho_bytes": t} for n, t in arquivos]}
    r = await api.post(BATCH, json=body, headers=await _h(api, acme))
    assert r.status_code == 422
    assert trecho in r.json()["detail"]
    async with tenant_session(acme.id) as db:
        assert (await db.scalars(select(Comprovante))).first() is None


async def test_lista_quais_arquivos_foram_recusados(
    api: httpx.AsyncClient, acme: DemoTenant, fila: list[Any]
) -> None:
    body = _declarar(("ok.pdf", b"1"), ("foto.heic", b"1"))
    erros = (await api.post(BATCH, json=body, headers=await _h(api, acme))).json()["errors"]
    assert erros == [
        {
            "campo": "arquivos.1",
            "arquivo": "foto.heic",
            "erro": "Formato HEIC não suportado. Envie JPEG, JPG, PDF, PNG.",
        }
    ]


# --- Envio, confirmação e validação ------------------------------------------------


async def test_fluxo_completo_pdf_e_imagem(
    api: httpx.AsyncClient, acme: DemoTenant, fila: list[Any], processar: Processar
) -> None:
    h = await _h(api, acme)
    lote = await _enviar(api, h, ("carne.pdf", A.pdf(3)), ("recibo.png", A.imagem("PNG")))

    antes = await _status(api, h, lote["batch_id"])
    assert (antes["em_andamento"], antes["concluidos"]) == (2, 0)
    assert {i["status"] for i in antes["itens"]} == {"validando"}
    assert len(fila) == 2

    await processar(fila)

    depois = await _status(api, h, lote["batch_id"])
    assert (depois["total"], depois["concluidos"], depois["com_erro"], depois["em_andamento"]) == (
        2,
        2,
        0,
        0,
    )
    por_nome = {i["nome"]: i for i in depois["itens"]}
    assert por_nome["carne.pdf"]["total_paginas"] == 3
    assert all(i["tem_miniatura"] for i in depois["itens"])
    async with tenant_session(acme.id) as db:
        comps = list(await db.scalars(select(Comprovante)))
    assert all(c.imutavel and c.sha256 and len(c.sha256) == 64 for c in comps)


async def test_arquivo_disfarcado_vai_para_quarentena(
    api: httpx.AsyncClient, acme: DemoTenant, fila: list[Any], processar: Processar
) -> None:
    h = await _h(api, acme)
    lote = await _enviar(api, h, ("boleto.pdf", A.EXECUTAVEL))
    original = urlparse(lote["itens"][0]["upload_url"]).path.split("/comprovantes-test/")[1]

    await processar(fila)

    item = (await _status(api, h, lote["batch_id"]))["itens"][0]
    assert item["status"] == "erro"
    assert "não é PDF" in item["erro_msg"]
    storage = comprovantes_storage()
    assert storage.head(original) is None
    assert storage.head(f"quarentena/{original}") is not None
    r = await api.get(f"/api/v1/comprovantes/{item['comprovante_id']}/arquivo", headers=h)
    assert r.status_code == 409  # arquivo recusado não é servido


async def test_storage_recusa_arquivo_maior_que_o_declarado(
    api: httpx.AsyncClient, acme: DemoTenant, fila: list[Any]
) -> None:
    h = await _h(api, acme)
    lote = (await api.post(BATCH, json=_declarar(("a.pdf", A.pdf())), headers=h)).json()
    item = lote["itens"][0]
    maior = A.pdf() + b"lixo extra"
    assert (await _put(item["upload_url"], maior, item["headers"])).status_code == 403
    tipo_errado = await _put(item["upload_url"], A.pdf(), {"Content-Type": "text/html"})
    assert tipo_errado.status_code == 403


async def test_confirmar_antes_de_enviar_e_idempotencia(
    api: httpx.AsyncClient, acme: DemoTenant, fila: list[Any]
) -> None:
    h = await _h(api, acme)
    data = A.pdf()
    lote = (await api.post(BATCH, json=_declarar(("a.pdf", data)), headers=h)).json()
    item = lote["itens"][0]
    completar = f"/api/v1/uploads/{item['comprovante_id']}/complete"

    assert (await api.post(completar, headers=h)).status_code == 409  # ainda não enviado
    await _put(item["upload_url"], data, item["headers"])
    assert (await api.post(completar, headers=h)).json() == {"status": "validando"}
    assert (await api.post(completar, headers=h)).json() == {"status": "validando"}
    assert len(fila) == 1  # enfileirado uma única vez


async def test_nova_url_so_enquanto_nao_enviado(
    api: httpx.AsyncClient, acme: DemoTenant, fila: list[Any]
) -> None:
    h = await _h(api, acme)
    data = A.imagem("JPEG")
    lote = (await api.post(BATCH, json=_declarar(("f.jpg", data)), headers=h)).json()
    cid = lote["itens"][0]["comprovante_id"]
    nova = await api.post(f"/api/v1/uploads/{cid}/retry-url", headers=h)
    assert nova.status_code == 200
    reenvio = await _put(nova.json()["upload_url"], data, nova.json()["headers"])
    assert reenvio.status_code == 200
    await api.post(f"/api/v1/uploads/{cid}/complete", headers=h)
    assert (await api.post(f"/api/v1/uploads/{cid}/retry-url", headers=h)).status_code == 409


async def test_marca_possivel_duplicado(
    api: httpx.AsyncClient, acme: DemoTenant, fila: list[Any], processar: Processar
) -> None:
    h = await _h(api, acme)
    mesmo = A.pdf(2)
    primeiro = await _enviar(api, h, ("a.pdf", mesmo))
    await processar(fila)
    segundo = await _enviar(api, h, ("copia.pdf", mesmo))
    await processar(fila)

    assert (await _status(api, h, primeiro["batch_id"]))["itens"][0]["possivel_duplicado"] is False
    assert (await _status(api, h, segundo["batch_id"]))["itens"][0]["possivel_duplicado"] is True


# --- Status do lote (cache Redis) -----------------------------------------------------


async def test_status_vem_do_cache_e_cai_no_banco_sem_ele(
    api: httpx.AsyncClient, acme: DemoTenant, fila: list[Any], fake_redis: FakeAsyncRedis
) -> None:
    h = await _h(api, acme)
    lote = await _enviar(api, h, ("a.pdf", A.pdf()))
    chave = f"batch:{lote['batch_id']}"
    # Mudança feita por fora da aplicação não aparece: a resposta vem do Redis,
    # mantido por quem altera o comprovante (API e worker).
    async with tenant_session(acme.id) as db:
        await db.execute(update(Comprovante).values(status_processamento="erro", erro_msg="x"))
    assert (await _status(api, h, lote["batch_id"]))["itens"][0]["status"] == "validando"

    await fake_redis.delete(chave)
    assert (await _status(api, h, lote["batch_id"]))["itens"][0]["status"] == "erro"
    assert await fake_redis.exists(chave)  # o banco repôs o cache


async def test_upload_e_status_funcionam_sem_redis(
    api: httpx.AsyncClient,
    acme: DemoTenant,
    fila: list[Any],
    processar: Processar,
    redis_server: FakeServer,
) -> None:
    h = await _h(api, acme)
    redis_server.connected = False
    lote = await _enviar(api, h, ("a.pdf", A.pdf()))
    await processar(fila)
    assert (await _status(api, h, lote["batch_id"]))["concluidos"] == 1


async def test_lote_em_cache_so_para_o_dono_ou_admin(
    api: httpx.AsyncClient, acme: DemoTenant, fila: list[Any]
) -> None:
    lote = await _enviar(api, await _h(api, acme), ("a.pdf", A.pdf()))
    url = f"{BATCH}/{lote['batch_id']}/status"
    assert (await api.get(url, headers=await _h(api, acme, "aprovador"))).status_code == 404
    assert (await api.get(url, headers=await _h(api, acme, "admin"))).status_code == 200


# --- Acesso aos arquivos -----------------------------------------------------------


async def test_download_seguro_e_miniatura_sem_exif(
    api: httpx.AsyncClient,
    acme: DemoTenant,
    globex: DemoTenant,
    fila: list[Any],
    processar: Processar,
) -> None:
    h = await _h(api, acme)
    lote = await _enviar(api, h, ("foto recibo.jpg", A.imagem("JPEG", exif=True)))
    await processar(fila)
    cid = lote["itens"][0]["comprovante_id"]

    arq = await api.get(f"/api/v1/comprovantes/{cid}/arquivo", headers=h)
    assert arq.status_code == 302
    disp = parse_qs(urlparse(arq.headers["location"]).query)["response-content-disposition"][0]
    assert disp == 'attachment; filename="foto recibo.jpg"'
    assert (await _get(arq.headers["location"])).status_code == 200

    mini = await api.get(f"/api/v1/comprovantes/{cid}/thumbnail", headers=h)
    conteudo = (await _get(mini.headers["location"])).content
    with Image.open(io.BytesIO(conteudo)) as img:
        assert img.format == "WEBP"
        assert img.width <= 320
        assert not img.getexif()  # sem metadados (nem GPS)

    # Outro colaborador / outra empresa não acessam.
    assert (
        await api.get(f"/api/v1/comprovantes/{cid}/arquivo", headers=await _h(api, globex, "admin"))
    ).status_code == 404
    assert (
        await api.get(
            f"/api/v1/uploads/batch/{lote['batch_id']}/status",
            headers=await _h(api, globex, "admin"),
        )
    ).status_code == 404


async def test_original_validado_nao_pode_ser_apagado(
    api: httpx.AsyncClient, acme: DemoTenant, fila: list[Any], processar: Processar
) -> None:
    h = await _h(api, acme)
    await _enviar(api, h, ("a.pdf", A.pdf()))
    await processar(fila)
    async with tenant_session(acme.id) as db:
        comp = await db.scalar(select(Comprovante))
    assert comp is not None
    s3 = get_s3_client()
    bucket = get_settings().s3_bucket_comprovantes
    versao = s3.head_object(Bucket=bucket, Key=comp.storage_key)["VersionId"]
    with pytest.raises(ClientError, match="AccessDenied"):
        s3.delete_object(Bucket=bucket, Key=comp.storage_key, VersionId=versao)


# --- Rotina de envios abandonados --------------------------------------------------


async def test_recupera_envios_abandonados(
    api: httpx.AsyncClient, acme: DemoTenant, fila: list[Any], lote_cache: LoteStatusCache
) -> None:
    h = await _h(api, acme)
    data = A.pdf()
    lote = (
        await api.post(BATCH, json=_declarar(("chegou.pdf", data), ("nunca.pdf", data)), headers=h)
    ).json()
    chegou = lote["itens"][0]
    await _put(chegou["upload_url"], data, chegou["headers"])  # sem /complete
    async with tenant_session(acme.id) as db:
        await db.execute(
            update(Comprovante).values(created_at=datetime.now(UTC) - timedelta(hours=1))
        )

    enfileirados: list[tuple[uuid.UUID, uuid.UUID]] = []
    resultado = await recuperar_abandonados(
        comprovantes_storage(), lambda t, c: enfileirados.append((t, c)), lote_cache
    )

    assert resultado == {"retomados": 1, "expirados": 1, "travados": 0}
    assert [str(c) for _, c in enfileirados] == [chegou["comprovante_id"]]
    itens = {i["nome"]: i for i in (await _status(api, h, lote["batch_id"]))["itens"]}
    assert itens["chegou.pdf"]["status"] == "validando"
    assert itens["nunca.pdf"]["status"] == "erro"


async def test_validacao_travada_termina_em_erro(
    api: httpx.AsyncClient, acme: DemoTenant, fila: list[Any], lote_cache: LoteStatusCache
) -> None:
    """Task perdida (worker derrubado no meio): o item não fica "validando" para sempre."""
    h = await _h(api, acme)
    lote = await _enviar(api, h, ("a.pdf", A.pdf()))  # confirmado, mas ninguém processa

    resultado = await recuperar_abandonados(
        comprovantes_storage(),
        lambda t, c: None,
        lote_cache,
        agora=datetime.now(UTC) + timedelta(hours=1),
    )

    assert resultado == {"retomados": 0, "expirados": 0, "travados": 1}
    item = (await _status(api, h, lote["batch_id"]))["itens"][0]
    assert (item["status"], item["erro_msg"]) == ("erro", FALHA_VALIDACAO)


async def test_falha_definitiva_da_validacao_responde_ao_usuario(
    api: httpx.AsyncClient, acme: DemoTenant, fila: list[Any], lote_cache: LoteStatusCache
) -> None:
    h = await _h(api, acme)
    lote = await _enviar(api, h, ("a.pdf", A.pdf()))
    tenant_id, comp_id = fila[0]

    await marcar_falha_validacao(tenant_id, comp_id, lote_cache)

    item = (await _status(api, h, lote["batch_id"]))["itens"][0]
    assert (item["status"], item["erro_msg"]) == ("erro", FALHA_VALIDACAO)


async def test_falha_na_miniatura_nao_impede_a_validacao(
    api: httpx.AsyncClient,
    acme: DemoTenant,
    fila: list[Any],
    processar: Processar,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def renderizador_quebrado(*_: object) -> bytes:
        raise RuntimeError("pdfium: página inválida")

    monkeypatch.setattr(validacao_service, "gerar_miniatura", renderizador_quebrado)
    h = await _h(api, acme)
    lote = await _enviar(api, h, ("a.pdf", A.pdf()))

    await processar(fila)

    item = (await _status(api, h, lote["batch_id"]))["itens"][0]
    assert (item["status"], item["tem_miniatura"]) == ("concluido", False)
    mini = await api.get(f"/api/v1/comprovantes/{item['comprovante_id']}/thumbnail", headers=h)
    assert mini.status_code == 404
