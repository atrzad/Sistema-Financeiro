"""Comandos administrativos.

uv run python -m app.cli seed      # cria empresas e usuários de demonstração
"""

import argparse
import asyncio
import uuid

from app.core.security import hash_password
from app.db.tenant import resolve_tenant, tenant_session
from app.models import Tenant, User

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
        if await resolve_tenant(slug):
            print(f"· {slug}: já existe, ignorado")
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
        print(f"✔ {slug}: {nome}")
        for _, local, role, _nivel in USUARIOS:
            print(f"    {role:<12} {local}@{dominio}")
    print(f"\nSenha de todos os usuários de demonstração: {SENHA_DEMO}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed", help="cria empresas e usuários de demonstração")
    args = parser.parse_args()
    if args.cmd == "seed":
        asyncio.run(seed())


if __name__ == "__main__":
    main()
