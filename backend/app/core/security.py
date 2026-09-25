"""Senhas (Argon2id), access tokens (JWT) e refresh tokens opacos."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import Settings

Role = Literal["admin", "aprovador", "colaborador"]

_hasher = PasswordHasher()  # parâmetros padrão do argon2-cffi (Argon2id, RFC 9106)

# Hash de uma senha qualquer, usado para gastar o mesmo tempo quando o usuário
# não existe — evita descobrir e-mails cadastrados pelo tempo de resposta.
DUMMY_PASSWORD_HASH = _hasher.hash("senha-que-nao-pertence-a-ninguem")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


# --- Access token (JWT) -------------------------------------------------------


@dataclass(frozen=True)
class AccessClaims:
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: Role
    nivel: int


class InvalidTokenError(Exception):
    pass


def create_access_token(claims: AccessClaims, settings: Settings) -> tuple[str, int]:
    """Retorna (token, expires_in_segundos)."""
    ttl = timedelta(minutes=settings.access_token_ttl_minutes)
    now = datetime.now(UTC)
    payload = {
        "sub": str(claims.user_id),
        "tid": str(claims.tenant_id),
        "role": claims.role,
        "nivel": claims.nivel,
        "typ": "access",
        "iat": now,
        "exp": now + ttl,
    }
    token = jwt.encode(
        payload, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm
    )
    return token, int(ttl.total_seconds())


def decode_access_token(token: str, settings: Settings) -> AccessClaims:
    try:
        data = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["sub", "tid", "role", "exp", "iat"]},
        )
        if data.get("typ") != "access":
            raise InvalidTokenError("tipo de token inválido")
        return AccessClaims(
            user_id=uuid.UUID(data["sub"]),
            tenant_id=uuid.UUID(data["tid"]),
            role=data["role"],
            nivel=int(data.get("nivel", 0)),
        )
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise InvalidTokenError(str(exc)) from exc


# --- Refresh token opaco ------------------------------------------------------
# Formato: "<tenant_id>.<aleatório>". O tenant_id (não secreto) permite abrir a
# transação com SET LOCAL antes de consultar refresh_tokens sob RLS. No banco
# guardamos apenas o SHA-256 do token inteiro.


def new_refresh_token(tenant_id: uuid.UUID) -> str:
    return f"{tenant_id}.{secrets.token_urlsafe(32)}"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def tenant_from_refresh_token(token: str) -> uuid.UUID:
    prefix, sep, rest = token.partition(".")
    if not sep or not rest:
        raise InvalidTokenError("refresh token malformado")
    try:
        return uuid.UUID(prefix)
    except ValueError as exc:
        raise InvalidTokenError("refresh token malformado") from exc
