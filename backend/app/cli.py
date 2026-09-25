"""Comandos administrativos.

uv run python -m app.cli seed      # cria empresas e usuários de demonstração
"""

import argparse
import asyncio
import json
import uuid
from pathlib import Path

from app.core.security import hash_password
from app.db.tenant import resolve_tenant, tenant_session
from app.models import Tenant, User
from app.services.cadastros_service import garantir_categorias_padrao

SENHA_DEMO = "Senha@123"

DEMO = {
    "acme": ("ACME Comércio Ltda", "acme.com.br"),
    "globex": ("Globex Serviços S.A.", "globex.com.br"),
}
USUARIOS = [
    ("Ana Admin", "admin", "admin", 2),
    ("Gabriel Gestor", "gestor", "aprovador", 2),
    ("Aline Aprovadora", "aprovador", "aprovador", 1),
    ("Carlos Colaborador", "colaborador", "colaborador", 0),
]


async def seed() -> None:
    senha_hash = hash_password(SENHA_DEMO)
    for slug, (nome, dominio) in DEMO.items():
        existente = await resolve_tenant(slug)
        if existente:
            async with tenant_session(existente) as db:
                novas = await garantir_categorias_padrao(db, existente)
            print(
                f"· {slug}: já existe" + (f" — {novas} categorias padrão criadas" if novas else "")
            )
            continue
        tenant_id = uuid.uuid4()
        async with tenant_session(tenant_id) as db:
            db.add(Tenant(id=tenant_id, nome=nome, slug=slug))
            await db.flush()
            for nome_user, local, role, nivel in USUARIOS:
                db.add(
                    User(
                        tenant_id=tenant_id,
                        nome=nome_user,
                        email=f"{local}@{dominio}",
                        password_hash=senha_hash,
                        role=role,
                        nivel_aprovacao=nivel,
                    )
                )
            await garantir_categorias_padrao(db, tenant_id)
        print(f"✔ {slug}: {nome}")
        for _, local, role, _nivel in USUARIOS:
            print(f"    {role:<12} {local}@{dominio}")
    print(f"\nSenha de todos os usuários de demonstração: {SENHA_DEMO}")


def exportar_openapi(destino: Path | None) -> None:
    """Contrato público da API (sem as rotas de debug, que só existem em ambiente local)."""
    from app.core.config import Environment, get_settings
    from app.main import create_app

    settings = get_settings().model_copy(update={"environment": Environment.PRODUCTION})
    conteudo = json.dumps(create_app(settings).openapi(), indent=2, ensure_ascii=False) + "\n"
    if destino:
        destino.write_text(conteudo, encoding="utf-8")
        print(f"OpenAPI exportado para {destino}")
    else:
        print(conteudo, end="")


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed", help="cria empresas e usuários de demonstração")
    p_openapi = sub.add_parser("openapi", help="exporta o contrato OpenAPI em JSON")
    p_openapi.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()
    if args.cmd == "seed":
        asyncio.run(seed())
    elif args.cmd == "openapi":
        exportar_openapi(args.out)


if __name__ == "__main__":
    main()
