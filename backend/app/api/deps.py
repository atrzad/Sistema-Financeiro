"""Dependências comuns: usuário autenticado, sessão com tenant e RBAC."""

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import ProblemError
from app.core.redis import get_redis
from app.core.security import AccessClaims, InvalidTokenError, Role, decode_access_token
from app.db.tenant import tenant_session
from app.services.auth_service import AuthService
from app.services.rate_limit import LoginRateLimiter

_bearer = HTTPBearer(auto_error=False)

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_auth_service(settings: SettingsDep) -> AuthService:
    limiter = LoginRateLimiter(
        get_redis(), settings.login_max_failures, settings.login_failure_window_s
    )
    return AuthService(settings, limiter)


def get_current_user(
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> AccessClaims:
    unauthorized = ProblemError(
        401, "Autenticação necessária.", headers={"WWW-Authenticate": "Bearer"}
    )
    if credentials is None:
        raise unauthorized
    try:
        return decode_access_token(credentials.credentials, settings)
    except InvalidTokenError:
        raise unauthorized from None


CurrentUser = Annotated[AccessClaims, Depends(get_current_user)]


async def get_db(user: CurrentUser) -> AsyncIterator[AsyncSession]:
    """Sessão de negócio: transação com SET LOCAL do tenant do usuário (RLS)."""
    async with tenant_session(user.tenant_id) as session:
        yield session


DB = Annotated[AsyncSession, Depends(get_db)]


def require_role(*roles: Role) -> Callable[[AccessClaims], Awaitable[AccessClaims]]:
    async def _check(user: CurrentUser) -> AccessClaims:
        if user.role not in roles:
            raise ProblemError(403, "Seu perfil não tem permissão para esta ação.")
        return user

    return _check
