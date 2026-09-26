"""Lançamentos manuais (H2.3, H2.4).

Visibilidade: colaborador vê e edita só os próprios; aprovador vê todos da
empresa; admin vê e edita todos. O RLS garante o isolamento entre empresas.
"""

import base64
import binascii
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, case, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import ProblemError
from app.core.security import AccessClaims
from app.domain.status import StatusEfetivo, dias_para_vencimento, status_efetivo
from app.models import Categoria, CentroCusto, Lancamento, Projeto, Supplier, Tag
from app.schemas.cadastros import SupplierRef
from app.schemas.lancamentos import (
    CentroCustoRef,
    LancamentoIn,
    LancamentoOut,
    LancamentoUpdate,
    Ref,
)

LIMITE_MAXIMO = 200

_RELACOES = (
    selectinload(Lancamento.supplier),
    selectinload(Lancamento.categoria),
    selectinload(Lancamento.projeto),
    selectinload(Lancamento.centro_custo),
    selectinload(Lancamento.usuario),
    selectinload(Lancamento.tags),
)


# --- Apresentação -----------------------------------------------------------------


def to_out(lanc: Lancamento, hoje: date) -> LancamentoOut:
    return LancamentoOut(
        id=lanc.id,
        valor=lanc.valor,
        data_emissao=lanc.data_emissao,
        data_pagamento_prevista=lanc.data_pagamento_prevista,
        data_pagamento_efetiva=lanc.data_pagamento_efetiva,
        supplier=SupplierRef.model_validate(lanc.supplier) if lanc.supplier else None,
        categoria=Ref.model_validate(lanc.categoria) if lanc.categoria else None,
        projeto=Ref.model_validate(lanc.projeto) if lanc.projeto else None,
        centro_custo=CentroCustoRef.model_validate(lanc.centro_custo)
        if lanc.centro_custo
        else None,
        tags=[Ref.model_validate(t) for t in lanc.tags],
        usuario=Ref(id=lanc.usuario.id, nome=lanc.usuario.nome),
        descricao=lanc.descricao,
        forma_pagamento=lanc.forma_pagamento,
        linha_digitavel=lanc.linha_digitavel,
        status=lanc.status,
        status_efetivo=status_efetivo(lanc.status, lanc.data_pagamento_prevista, hoje),
        dias_para_vencimento=dias_para_vencimento(lanc.data_pagamento_prevista, hoje),
        status_aprovacao=lanc.status_aprovacao,
        version=lanc.version,
        created_at=lanc.created_at,
        updated_at=lanc.updated_at,
    )


# --- Regras de acesso ---------------------------------------------------------------


def _visiveis(user: AccessClaims) -> Select[Lancamento]:
    query = select(Lancamento).where(Lancamento.deleted_at.is_(None)).options(*_RELACOES)
    if user.role == "colaborador":
        query = query.where(Lancamento.usuario_id == user.user_id)
    return query


def _pode_editar(user: AccessClaims, lanc: Lancamento) -> bool:
    return user.role == "admin" or lanc.usuario_id == user.user_id


async def _validar_referencias(db: AsyncSession, dados: dict[str, Any]) -> None:
    """Garante que os IDs referenciados existem na empresa e estão ativos.

    Necessário porque a checagem de FK do Postgres ignora o RLS: sem isto, seria
    possível apontar para um fornecedor de OUTRA empresa conhecendo o UUID.
    """
    checagens: list[tuple[str, Any, str]] = [
        ("supplier_id", Supplier, "Fornecedor"),
        ("categoria_id", Categoria, "Categoria"),
        ("projeto_id", Projeto, "Projeto"),
        ("centro_custo_id", CentroCusto, "Centro de custo"),
    ]
    for campo, model, rotulo in checagens:
        ref_id = dados.get(campo)
        if ref_id is None:
            continue
        obj = await db.get(model, ref_id)  # sob RLS: outra empresa = None
        inativo = obj is not None and (
            getattr(obj, "deleted_at", None) is not None or getattr(obj, "ativo", True) is False
        )
        if obj is None or inativo:
            raise ProblemError(
                422,
                f"{rotulo} inexistente ou inativo.",
                errors=[{"campo": campo, "erro": "inválido"}],
            )


async def _tags(db: AsyncSession, ids: list[uuid.UUID], atuais: list[Tag]) -> list[Tag]:
    """Tags pedidas, validadas sob RLS. Uma tag desativada continua nos lançamentos
    que já a tinham, mas não pode ser adicionada a outros."""
    ids = list(dict.fromkeys(ids))
    if not ids:
        return []
    encontradas = {t.id: t for t in await db.scalars(select(Tag).where(Tag.id.in_(ids)))}
    ja_tinha = {t.id for t in atuais}
    invalidas = [
        i for i in ids if i not in encontradas or (not encontradas[i].ativo and i not in ja_tinha)
    ]
    if invalidas:
        raise ProblemError(
            422,
            "Tag inexistente ou inativa.",
            errors=[{"campo": "tag_ids", "erro": "inválido", "ids": [str(i) for i in invalidas]}],
        )
    return [encontradas[i] for i in ids]


# --- Casos de uso ---------------------------------------------------------------------


async def obter(db: AsyncSession, user: AccessClaims, lanc_id: uuid.UUID) -> Lancamento:
    lanc = await db.scalar(_visiveis(user).where(Lancamento.id == lanc_id))
    if lanc is None:
        raise ProblemError(404, "Lançamento não encontrado.")
    return lanc


async def criar(db: AsyncSession, user: AccessClaims, data: LancamentoIn) -> Lancamento:
    dados = data.model_dump()
    tag_ids = dados.pop("tag_ids")
    await _validar_referencias(db, dados)
    lanc = Lancamento(tenant_id=user.tenant_id, usuario_id=user.user_id, **dados)
    lanc.tags = await _tags(db, tag_ids, [])
    db.add(lanc)
    await db.flush()
    lanc_id = lanc.id
    # Relê do banco: a coleção montada em memória ficaria na ordem do pedido.
    db.expire(lanc)
    return await obter(db, user, lanc_id)


def _versao_esperada(if_match: str | None) -> int | None:
    if if_match is None:
        return None
    try:
        return int(if_match.removeprefix("W/").strip().strip('"'))
    except ValueError:
        raise ProblemError(400, "Cabeçalho If-Match inválido.") from None


async def atualizar(
    db: AsyncSession,
    user: AccessClaims,
    lanc_id: uuid.UUID,
    data: LancamentoUpdate,
    if_match: str | None,
) -> Lancamento:
    lanc = await obter(db, user, lanc_id)
    if not _pode_editar(user, lanc):
        raise ProblemError(403, "Você só pode editar os seus próprios lançamentos.")

    esperada = _versao_esperada(if_match)
    if esperada is not None and esperada != lanc.version:
        raise ProblemError(
            412,
            "Este lançamento foi alterado por outra pessoa. Recarregue e tente novamente.",
            versao_atual=lanc.version,
        )

    changes = data.model_dump(exclude_unset=True)
    if "valor" in changes and changes["valor"] is None:
        raise ProblemError(422, "Valor é obrigatório.")
    if "data_emissao" in changes and changes["data_emissao"] is None:
        raise ProblemError(422, "Data de emissão é obrigatória.")
    if lanc.status == "pago":
        bloqueados = {"valor", "data_pagamento_prevista"} & {
            k for k, v in changes.items() if v != getattr(lanc, k)
        }
        if bloqueados:
            raise ProblemError(409, "Lançamento pago: valor e vencimento não podem ser alterados.")

    if "tag_ids" in changes:
        lanc.tags = await _tags(db, changes.pop("tag_ids") or [], lanc.tags)
    await _validar_referencias(db, changes)
    for k, v in changes.items():
        setattr(lanc, k, v)
    lanc.version += 1
    await db.flush()
    db.expire(lanc)
    return await obter(db, user, lanc_id)


async def excluir(db: AsyncSession, user: AccessClaims, lanc_id: uuid.UUID) -> None:
    lanc = await obter(db, user, lanc_id)
    if not _pode_editar(user, lanc):
        raise ProblemError(403, "Você só pode excluir os seus próprios lançamentos.")
    if lanc.status == "pago":
        raise ProblemError(409, "Lançamentos pagos não podem ser excluídos.")
    lanc.deleted_at = datetime.now(UTC)
    lanc.version += 1
    await db.flush()


# --- Listagem com filtros e paginação por cursor -------------------------------------


def status_efetivo_sql(hoje: date) -> ColumnElement[str]:
    """Mesma regra de domain.status.status_efetivo, em SQL (com 'hoje' parametrizado)."""
    prevista = Lancamento.data_pagamento_prevista
    return case(
        (Lancamento.status.in_(["pago", "rejeitado"]), Lancamento.status),
        (prevista < literal(hoje), literal("atrasado")),
        (prevista == literal(hoje), literal("vence_hoje")),
        else_=Lancamento.status,
    )


@dataclass(frozen=True)
class Filtros:
    status: list[StatusEfetivo] | None = None
    supplier_id: uuid.UUID | None = None
    categoria_id: uuid.UUID | None = None
    projeto_id: uuid.UUID | None = None
    centro_custo_id: uuid.UUID | None = None
    vencimento_de: date | None = None
    vencimento_ate: date | None = None
    tag_ids: tuple[uuid.UUID, ...] = ()  # o lançamento precisa ter todas


def _encode_cursor(lanc: Lancamento) -> str:
    raw = json.dumps(
        {
            "p": lanc.data_pagamento_prevista.isoformat() if lanc.data_pagamento_prevista else None,
            "i": str(lanc.id),
        }
    )
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[date | None, uuid.UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        data = json.loads(raw)
        prevista = date.fromisoformat(data["p"]) if data["p"] else None
        return prevista, uuid.UUID(data["i"])
    except (ValueError, KeyError, TypeError, binascii.Error, json.JSONDecodeError):
        raise ProblemError(400, "Cursor de paginação inválido.") from None


async def listar(
    db: AsyncSession,
    user: AccessClaims,
    filtros: Filtros,
    hoje: date,
    limit: int = 50,
    cursor: str | None = None,
) -> tuple[list[Lancamento], str | None]:
    limit = max(1, min(limit, LIMITE_MAXIMO))
    prevista = Lancamento.data_pagamento_prevista
    query = _visiveis(user)

    if filtros.status:
        query = query.where(status_efetivo_sql(hoje).in_([s.value for s in filtros.status]))
    for campo in ("supplier_id", "categoria_id", "projeto_id", "centro_custo_id"):
        valor = getattr(filtros, campo)
        if valor is not None:
            query = query.where(getattr(Lancamento, campo) == valor)
    for tag_id in dict.fromkeys(filtros.tag_ids):
        query = query.where(Lancamento.tags.any(Tag.id == tag_id))
    if filtros.vencimento_de:
        query = query.where(prevista >= filtros.vencimento_de)
    if filtros.vencimento_ate:
        query = query.where(prevista <= filtros.vencimento_ate)

    if cursor:
        c_prev, c_id = _decode_cursor(cursor)
        if c_prev is not None:
            query = query.where(
                or_(
                    prevista > c_prev,
                    and_(prevista == c_prev, Lancamento.id > c_id),
                    prevista.is_(None),
                )
            )
        else:
            query = query.where(prevista.is_(None), Lancamento.id > c_id)

    query = query.order_by(prevista.asc().nulls_last(), Lancamento.id.asc()).limit(limit + 1)
    rows = list(await db.scalars(query))
    proximo = _encode_cursor(rows[limit - 1]) if len(rows) > limit else None
    return rows[:limit], proximo
