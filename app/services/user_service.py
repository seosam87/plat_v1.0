import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User).where(User.email == email.lower().strip())
    )
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    username: str,
    email: str,
    password_hash: str,
    role: UserRole = UserRole.client,
) -> User:
    from app.services.audit_service import log_action

    user = User(
        username=username,
        email=email.lower().strip(),
        password_hash=password_hash,
        role=role,
    )
    db.add(user)
    await db.flush()  # assigns id; caller session commits
    await log_action(
        db,
        action="user.created",
        user_id=None,
        entity_type="user",
        entity_id=str(user.id),
        detail={"role": role.value},
    )
    return user


async def list_users(db: AsyncSession, current_user: User) -> list[User]:
    """Admin only: return all users ordered by created_at."""
    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin only")
    result = await db.execute(select(User).order_by(User.created_at))
    return list(result.scalars().all())


async def update_user(
    db: AsyncSession,
    target_user_id: str,
    current_user: User,
    username: str | None = None,
    email: str | None = None,
    role: UserRole | None = None,
) -> User:
    """Admin only: update user fields."""
    from app.services.audit_service import log_action

    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin only")
    user = await get_user_by_id(db, target_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if username is not None:
        user.username = username
    if email is not None:
        user.email = email.lower().strip()
    if role is not None:
        user.role = role
    await db.flush()
    await log_action(
        db,
        action="user.updated",
        user_id=current_user.id,
        entity_type="user",
        entity_id=str(user.id),
    )
    return user


async def deactivate_user(
    db: AsyncSession, target_user_id: str, current_user: User
) -> User:
    """Admin only: soft-delete by setting is_active=False."""
    from app.services.audit_service import log_action

    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin only")
    user = await get_user_by_id(db, target_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = False
    await db.flush()
    await log_action(
        db,
        action="user.deactivated",
        user_id=current_user.id,
        entity_type="user",
        entity_id=str(user.id),
    )
    return user


async def activate_user(
    db: AsyncSession, target_user_id: str, current_user: User
) -> User:
    """Admin only: re-activate a deactivated user."""
    from app.services.audit_service import log_action

    if current_user.role != UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin only")
    user = await get_user_by_id(db, target_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = True
    await db.flush()
    await log_action(
        db,
        action="user.activated",
        user_id=current_user.id,
        entity_type="user",
        entity_id=str(user.id),
    )
    return user
