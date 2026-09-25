from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Request, Response, status

from app.api.deps import DB, CurrentUser, SettingsDep, get_auth_service
from app.core.errors import ProblemError
from app.schemas.auth import LoginRequest, Me, TokenResponse
from app.services.auth_service import AuthService, Session, get_me

router = APIRouter(tags=["autenticação"])

REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"

AuthDep = Annotated[AuthService, Depends(get_auth_service)]
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


def _respond(response: Response, session: Session, settings: SettingsDep) -> TokenResponse:
    response.set_cookie(
        REFRESH_COOKIE,
        session.refresh_token,
        max_age=settings.refresh_token_ttl_days * 86400,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"
    return TokenResponse(
        access_token=session.access_token, expires_in=session.expires_in, user=session.me
    )


@router.post("/auth/login", response_model=TokenResponse)
async def login(
    body: LoginRequest, request: Request, response: Response, auth: AuthDep, settings: SettingsDep
) -> TokenResponse:
    """Entra com empresa (slug), e-mail e senha. O refresh token vai em cookie HttpOnly."""
    ip = request.client.host if request.client else "desconhecido"
    session = await auth.login(body.tenant_slug, body.email, body.senha, ip)
    return _respond(response, session, settings)


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh(
    response: Response, auth: AuthDep, settings: SettingsDep, refresh_token: RefreshCookie = None
) -> TokenResponse:
    """Troca o refresh token (cookie) por um novo par de tokens (rotação)."""
    session = await auth.refresh(refresh_token)
    return _respond(response, session, settings)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response, auth: AuthDep, settings: SettingsDep, refresh_token: RefreshCookie = None
) -> Response:
    await auth.logout(refresh_token)
    response.status_code = status.HTTP_204_NO_CONTENT
    response.delete_cookie(
        REFRESH_COOKIE,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
    )
    return response


@router.get("/me", response_model=Me)
async def me(user: CurrentUser, db: DB) -> Me:
    result = await get_me(db, user.user_id)
    if result is None:
        raise ProblemError(401, "Usuário não encontrado.")
    return result
