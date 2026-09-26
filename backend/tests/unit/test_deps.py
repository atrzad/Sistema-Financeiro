from typing import get_args

from fastapi.params import Depends

from app.api.deps import DB, get_db


def test_commit_acontece_antes_da_resposta() -> None:
    """No escopo padrão ("request"), o FastAPI envia a resposta e só depois fecha a
    sessão: o cliente veria 201 de algo ainda não gravado (ou que falhou no commit)."""
    dep = get_args(DB)[1]
    assert isinstance(dep, Depends)
    assert dep.dependency is get_db
    assert dep.scope == "function"
