"""A regra de status efetivo existe em dois lugares (Python e SQL). Precisam concordar sempre."""

from datetime import date, timedelta

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import select, text
from sqlalchemy.dialects import postgresql

from app.db.session import get_sessionmaker
from app.domain.clock import hoje_negocio
from app.domain.status import StatusArmazenado, status_efetivo
from app.models import Lancamento
from app.services.lancamento_service import status_efetivo_sql
from tests.conftest import DemoTenant

datas = st.dates(min_value=date(2020, 1, 1), max_value=date(2035, 12, 31))


async def _sql(status: str, prevista: date | None, hoje: date) -> str:
    """Avalia a MESMA expressão usada na listagem sobre uma linha virtual (nada é gravado)."""
    expr = status_efetivo_sql(hoje).compile(
        dialect=postgresql.dialect(),  # type: ignore[no-untyped-call]
        compile_kwargs={"literal_binds": True},
    )
    sql = str(expr).replace("lancamentos.", "l.")
    linha = "SELECT CAST(:s AS varchar) AS status, CAST(:p AS date) AS data_pagamento_prevista"
    async with get_sessionmaker()() as db:
        result = await db.execute(
            text(f"SELECT {sql} FROM ({linha}) AS l"),  # noqa: S608 — SQL gerado pelo próprio código
            {"s": status, "p": prevista},
        )
        return str(result.scalar_one())


@settings(
    max_examples=60, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture]
)
@given(
    status=st.sampled_from([s.value for s in StatusArmazenado]),
    prevista=st.one_of(st.none(), datas),
    hoje=datas,
)
async def test_python_e_sql_concordam(
    database: None, status: str, prevista: date | None, hoje: date
) -> None:
    assert await _sql(status, prevista, hoje) == status_efetivo(status, prevista, hoje).value


async def test_view_do_banco_concorda_com_o_dominio(acme: DemoTenant) -> None:
    """A view v_lancamentos usa hoje_negocio() do banco; o domínio usa o relógio Python."""
    from app.db.tenant import tenant_session
    from app.models import User

    hoje = hoje_negocio()
    casos = [
        ("pendente", hoje - timedelta(days=1)),
        ("pendente", hoje),
        ("pendente", hoje + timedelta(days=1)),
        ("reagendado", hoje - timedelta(days=3)),
        ("pendente", None),
    ]
    async with tenant_session(acme.id) as db:
        user = await db.scalar(select(User).limit(1))
        assert user is not None
        for status, prevista in casos:
            db.add(
                Lancamento(
                    tenant_id=acme.id,
                    usuario_id=user.id,
                    valor=1,
                    data_emissao=hoje,
                    status=status,
                    data_pagamento_prevista=prevista,
                )
            )
        await db.flush()
        rows = (
            await db.execute(
                text("SELECT status, data_pagamento_prevista, status_efetivo FROM v_lancamentos")
            )
        ).all()

    assert len(rows) == len(casos)
    for status, prevista, efetivo in rows:
        assert efetivo == status_efetivo(status, prevista, hoje).value
