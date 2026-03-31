from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.auth.password import hash_password
from app.dependencies import get_db
from app.models.user import User, UserRole
from app.services.user_service import (
    create_user,
    deactivate_user,
    list_users,
    update_user,
)

router = APIRouter(prefix="/admin", tags=["admin"])


class UserOut(BaseModel):
    id: str
    username: str
    email: str
    role: str
    is_active: bool


class CreateUserRequest(BaseModel):
    username: str
    email: EmailStr
    password: str
    role: UserRole = UserRole.client


class UpdateUserRequest(BaseModel):
    username: str | None = None
    email: EmailStr | None = None
    role: UserRole | None = None


def _user_out(user: User) -> UserOut:
    return UserOut(
        id=str(user.id),
        username=user.username,
        email=user.email,
        role=user.role.value,
        is_active=user.is_active,
    )


@router.get("/users", response_model=list[UserOut])
async def list_all_users(
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[UserOut]:
    users = await list_users(db, current_user)
    return [_user_out(u) for u in users]


@router.post("/users", response_model=UserOut, status_code=201)
async def create_new_user(
    body: CreateUserRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await create_user(
        db,
        username=body.username,
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
    )
    return _user_out(user)


@router.put("/users/{user_id}", response_model=UserOut)
async def edit_user(
    user_id: str,
    body: UpdateUserRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await update_user(
        db,
        target_user_id=user_id,
        current_user=current_user,
        username=body.username,
        email=body.email,
        role=body.role,
    )
    return _user_out(user)


@router.delete("/users/{user_id}", response_model=UserOut)
async def deactivate(
    user_id: str,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await deactivate_user(db, user_id, current_user)
    return _user_out(user)
