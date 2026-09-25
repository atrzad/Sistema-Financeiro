import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.deps import DB, require_role
from app.core.security import AccessClaims
from app.schemas.users import UserCreate, UserOut, UserUpdate
from app.services import user_service

router = APIRouter(prefix="/users", tags=["usuários"])

Admin = Annotated[AccessClaims, Depends(require_role("admin"))]


@router.get("", response_model=list[UserOut])
async def list_users(_: Admin, db: DB) -> list[UserOut]:
    return [UserOut.model_validate(u) for u in await user_service.list_users(db)]


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, admin: Admin, db: DB) -> UserOut:
    user = await user_service.create_user(db, admin.tenant_id, body)
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(user_id: uuid.UUID, body: UserUpdate, admin: Admin, db: DB) -> UserOut:
    user = await user_service.update_user(db, user_id, body, acting_user_id=admin.user_id)
    return UserOut.model_validate(user)
