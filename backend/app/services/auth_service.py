"""Casos de uso de autenticação: login, rotação de refresh token e logout."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import NoReturn

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ProblemError
from app.core.logging import get_logger
from app.core.security import (
    DUMMY_PASSWORD_HASH,
    AccessClaims,
    InvalidTokenError,
    Role,
    create_access_token,
    hash_token,
    new_refresh_token,
    tenant_from_refresh_token,
    verify_password,
)
from app.db.tenant import resolve_tenant, tenant_session
from app.models import RefreshToken, Tenant, User
from app.schemas.auth import Me, TenantInfo
from app.services.rate_limit import LoginRateLimiter

log = get_logger("auth")

CREDENCIAIS_INVALIDAS = "Empresa, e-mail ou senha incorretos."
SESSAO_EXPIRADA = "Sessão expirada. Entre novamente."


@dataclass(frozen=True)
class Session:
    access_token: str
    expires_in: int
    refresh_token: str
    me: Me


def build_me(user: User, tenant: Tenant) -> Me:
    role: Role = user.role  # type: ignore[assignment]
    return Me(
        id=user.id,
        nome=user.nome,
        email=user.email,
        role=role,
        nivel_aprovacao=user.nivel_aprovacao,
        tenant=TenantInfo(id=tenant.id, nome=tenant.nome, slug=tenant.slug),
    )


class AuthService:
    def __init__(self, settings: Settings, limiter: LoginRateLimiter) -> None:
        self.settings = settings
        self.limiter = limiter

    # --- helpers -----------------------------------------------------------

    async def _issue(
        self, db: AsyncSession, user: User, tenant: Tenant, family_id: uuid.UUID
    ) -> Session:
        refresh = new_refresh_token(tenant.id)
        db.add(
            RefreshToken(
                tenant_id=tenant.id,
                user_id=user.id,
                token_hash=hash_token(refresh),
                family_id=family_id,
                expires_at=datetime.now(UTC) + timedelta(days=self.settings.refresh_token_ttl_days),
            )
        )
        access, expires_in = create_access_token(
            AccessClaims(
                user_id=user.id,
                tenant_id=tenant.id,
                role=user.role,  # type: ignore[arg-type]
                nivel=user.nivel_aprovacao,
            ),
            self.settings,
        )
        return Session(access, expires_in, refresh, build_me(user, tenant))

    @staticmethod
    async def _revoke_family(db: AsyncSession, family_id: uuid.UUID) -> None:
        await db.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )

    # --- casos de uso --------------------------------------------------------

    async def login(self, tenant_slug: str, email: str, senha: str, ip: str) -> Session:
        retry = await self.limiter.retry_after(tenant_slug, email, ip)
        if retry is not None:
            raise ProblemError(
                429,
                f"Muitas tentativas de login. Tente novamente em {retry // 60 + 1} min.",
                headers={"Retry-After": str(retry)},
            )

        tenant_id = await resolve_tenant(tenant_slug)
        if tenant_id is None:
            verify_password(DUMMY_PASSWORD_HASH, senha)  # mesmo custo de tempo
            await self._fail(tenant_slug, email, ip, motivo="tenant_inexistente")

        async with tenant_session(tenant_id) as db:
            user = await db.scalar(select(User).where(User.email == email))
            ok = verify_password(user.password_hash if user else DUMMY_PASSWORD_HASH, senha)
            if user is None or not ok or not user.ativo:
                motivo = "senha" if user and not ok else "usuario_inexistente_ou_inativo"
                await self._fail(tenant_slug, email, ip, motivo=motivo)
            tenant = await db.get_one(Tenant, tenant_id)
            user.ultimo_login_em = datetime.now(UTC)
            session = await self._issue(db, user, tenant, family_id=uuid.uuid4())

        await self.limiter.reset(tenant_slug, email, ip)
        log.info("login_ok", tenant_id=str(tenant_id), user_id=str(session.me.id))
        return session

    async def _fail(self, tenant_slug: str, email: str, ip: str, *, motivo: str) -> NoReturn:
        await self.limiter.register_failure(tenant_slug, email, ip)
        log.info("login_falhou", tenant=tenant_slug, motivo=motivo)
        raise ProblemError(401, CREDENCIAIS_INVALIDAS)

    async def refresh(self, token: str | None) -> Session:
        if not token:
            raise ProblemError(401, SESSAO_EXPIRADA)
        try:
            tenant_id = tenant_from_refresh_token(token)
        except InvalidTokenError:
            raise ProblemError(401, SESSAO_EXPIRADA) from None

        # O bloco sempre termina com commit; a decisão de erro é tomada fora dele
        # para que a revogação da família (detecção de reuso) seja persistida.
        erro: str | None = None
        session: Session | None = None
        async with tenant_session(tenant_id) as db:
            stored = await db.scalar(
                select(RefreshToken)
                .where(RefreshToken.token_hash == hash_token(token))
                .with_for_update()
            )
            if stored is None:
                erro = "desconhecido"
            elif stored.revoked_at is not None:
                # Token já usado sendo reapresentado: possível roubo. Derruba a sessão inteira.
                await self._revoke_family(db, stored.family_id)
                erro = "reuso_detectado"
            elif stored.expires_at <= datetime.now(UTC):
                erro = "expirado"
            else:
                user = await db.get(User, stored.user_id)
                if user is None or not user.ativo:
                    await self._revoke_family(db, stored.family_id)
                    erro = "usuario_inativo"
                else:
                    stored.revoked_at = datetime.now(UTC)
                    tenant = await db.get_one(Tenant, tenant_id)
                    session = await self._issue(db, user, tenant, family_id=stored.family_id)

        if erro or session is None:
            log.warning("refresh_negado", tenant_id=str(tenant_id), motivo=erro)
            raise ProblemError(401, SESSAO_EXPIRADA)
        return session

    async def logout(self, token: str | None) -> None:
        if not token:
            return
        try:
            tenant_id = tenant_from_refresh_token(token)
        except InvalidTokenError:
            return
        async with tenant_session(tenant_id) as db:
            stored = await db.scalar(
                select(RefreshToken).where(RefreshToken.token_hash == hash_token(token))
            )
            if stored is not None:
                await self._revoke_family(db, stored.family_id)


async def get_me(db: AsyncSession, user_id: uuid.UUID) -> Me | None:
    user = await db.get(User, user_id)
    if user is None:
        return None
    tenant = await db.get_one(Tenant, user.tenant_id)
    return build_me(user, tenant)
