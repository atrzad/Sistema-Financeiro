"""H2.4: a listagem padrão (ordenada por vencimento) usa o índice mesmo com RLS."""

from sqlalchemy import select, text

from app.core.security import AccessClaims
from app.db.tenant import tenant_session
from app.domain.clock import hoje_negocio
from app.models import Lancamento, User
from app.services import lancamento_service as svc
from tests.conftest import DemoTenant, _owner_exec


async def test_listagem_usa_indice_de_vencimento(acme: DemoTenant, globex: DemoTenant) -> None:
    for t in (acme, globex):
        async with tenant_session(t.id) as db:
            await db.execute(
                text("""
                    INSERT INTO lancamentos (tenant_id, usuario_id, valor, data_emissao,
                                             data_pagamento_prevista)
                    SELECT :t, :u, 10 + g, DATE '2026-01-01',
                           DATE '2026-01-01' + (g % 365)
                    FROM generate_series(1, 10000) AS g
                """),
                {"t": str(t.id), "u": str(t.users["admin"].id)},
            )
    await _owner_exec("ANALYZE lancamentos")

    admin = acme.users["admin"]
    claims = AccessClaims(admin.id, acme.id, "admin", 2)
    async with tenant_session(acme.id) as db:
        user = await db.scalar(select(User).where(User.id == admin.id))
        assert user is not None
        query = (
            svc._visiveis(claims)
            .order_by(Lancamento.data_pagamento_prevista.asc().nulls_last(), Lancamento.id)
            .limit(51)
        )
        compiled = query.compile(compile_kwargs={"literal_binds": True})
        plano = "\n".join(r[0] for r in (await db.execute(text(f"EXPLAIN {compiled}"))).all())
        itens, _ = await svc.listar(db, claims, svc.Filtros(), hoje_negocio(), limit=50)

    assert "ix_lanc_vencimento" in plano, plano
    assert len(itens) == 50
