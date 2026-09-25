import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.core.config import Settings
from app.core.security import (
    AccessClaims,
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_token,
    new_refresh_token,
    tenant_from_refresh_token,
    verify_password,
)


def test_hash_e_verificacao_de_senha() -> None:
    h = hash_password("Senha@123")
    assert h.startswith("$argon2id$")
    assert verify_password(h, "Senha@123")
    assert not verify_password(h, "senha@123")
    assert not verify_password("hash-invalido", "Senha@123")


def test_access_token_ida_e_volta(make_settings: Callable[..., Settings]) -> None:
    s = make_settings()
    claims = AccessClaims(uuid.uuid4(), uuid.uuid4(), "aprovador", 2)
    token, expires_in = create_access_token(claims, s)
    assert expires_in == 15 * 60
    assert decode_access_token(token, s) == claims


def test_access_token_expirado_e_rejeitado(make_settings: Callable[..., Settings]) -> None:
    s = make_settings()
    past = datetime.now(UTC) - timedelta(hours=1)
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "tid": str(uuid.uuid4()),
            "role": "admin",
            "typ": "access",
            "iat": past,
            "exp": past + timedelta(minutes=15),
        },
        s.jwt_secret.get_secret_value(),
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, s)


def test_token_assinado_com_outro_segredo_e_rejeitado(
    make_settings: Callable[..., Settings],
) -> None:
    claims = AccessClaims(uuid.uuid4(), uuid.uuid4(), "admin", 2)
    token, _ = create_access_token(claims, make_settings(jwt_secret="x" * 40))
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, make_settings())


def test_token_sem_tipo_access_e_rejeitado(make_settings: Callable[..., Settings]) -> None:
    s = make_settings()
    now = datetime.now(UTC)
    token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "tid": str(uuid.uuid4()),
            "role": "admin",
            "iat": now,
            "exp": now + timedelta(minutes=5),
        },
        s.jwt_secret.get_secret_value(),
    )
    with pytest.raises(InvalidTokenError):
        decode_access_token(token, s)


def test_refresh_token_carrega_tenant_e_e_unico() -> None:
    tid = uuid.uuid4()
    a, b = new_refresh_token(tid), new_refresh_token(tid)
    assert a != b
    assert tenant_from_refresh_token(a) == tid
    assert len(hash_token(a)) == 64


@pytest.mark.parametrize("malformado", ["", "semponto", "nao-e-uuid.abc", "."])
def test_refresh_token_malformado(malformado: str) -> None:
    with pytest.raises(InvalidTokenError):
        tenant_from_refresh_token(malformado)


def test_segredo_jwt_curto_e_recusado(make_settings: Callable[..., Settings]) -> None:
    with pytest.raises(ValueError, match="jwt_secret"):
        make_settings(jwt_secret="curto")
