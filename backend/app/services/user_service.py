"""Gestão de usuários do tenant (H1.6). O tenant vem sempre da sessão, nunca do corpo."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ProblemError
from app.core.security import hash_password
from app.models import RefreshToken, User
from app.schemas.users import UserCreate, UserUpdate, _validar_nivel


async def list_users(db: AsyncSession) -> list[User]:
    result = await db.scalars(select(User).order_by(User.nome))
    return list(result)


async def create_user(db: AsyncSession, tenant_id: uuid.UUID, data: UserCreate) -> User:
    user = User(
        tenant_id=tenant_id,
        nome=data.nome.strip(),
        email=data.email,
        password_hash=hash_password(data.senha),
        role=data.role,
        nivel_aprovacao=data.nivel_aprovacao,
    )
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        raise ProblemError(409, "Já existe um usuário com este e-mail nesta empresa.") from None
    await db.refresh(user)
    return user


async def update_user(
    db: AsyncSession, user_id: uuid.UUID, data: UserUpdate, *, acting_user_id: uuid.UUID
) -> User:
    user = await db.get(User, user_id, with_for_update=True)
    if user is None:
        raise ProblemError(404, "Usuário não encontrado.")

    changes = data.model_dump(exclude_unset=True)
    novo_role = changes.get("role", user.role)
    novo_nivel = changes.get("nivel_aprovacao", user.nivel_aprovacao)
    if novo_role == "colaborador" and "nivel_aprovacao" not in changes:
        novo_nivel = 0
    try:
        _validar_nivel(novo_role, novo_nivel)
    except ValueError as exc:
        raise ProblemError(422, str(exc)) from None

    if user.id == acting_user_id:
        if changes.get("ativo") is False:
            raise ProblemError(409, "Você não pode desativar o seu próprio usuário.")
        if novo_role != "admin":
            raise ProblemError(409, "Você não pode remover o seu próprio papel de administrador.")

    if "nome" in changes and changes["nome"] is not None:
        user.nome = changes["nome"].strip()
    user.role = novo_role
    user.nivel_aprovacao = novo_nivel
    if "ativo" in changes and changes["ativo"] is not None:
        user.ativo = changes["ativo"]
        if not user.ativo:
            # Desativado: derruba todas as sessões imediatamente.
            await db.execute(
                update(RefreshToken)
                .where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
                .values(revoked_at=datetime.now(UTC))
            )
    await db.flush()
    await db.refresh(user)
    return user
