import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserRole
from app.services import crypto_service


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


# ---------------------------------------------------------------------------
# Per-user Anthropic API key management (Phase 16 LLM-01)
# ---------------------------------------------------------------------------


async def set_anthropic_api_key(db: AsyncSession, user: User, raw_key: str) -> None:
    """Encrypt and store the user's Anthropic API key.

    Args:
        db: Async database session.
        user: The User ORM object to update.
        raw_key: The plaintext Anthropic API key (e.g. "sk-ant-...").
    """
    user.anthropic_api_key_encrypted = crypto_service.encrypt(raw_key)
    await db.flush()


async def get_anthropic_api_key(db: AsyncSession, user: User) -> str | None:
    """Decrypt and return the user's Anthropic API key, or None if not set.

    Args:
        db: Async database session (unused but kept for consistent interface).
        user: The User ORM object.

    Returns:
        Plaintext API key string, or None if no key is stored.
    """
    if not user.anthropic_api_key_encrypted:
        return None
    return crypto_service.decrypt(user.anthropic_api_key_encrypted)


async def clear_anthropic_api_key(db: AsyncSession, user: User) -> None:
    """Remove the user's stored Anthropic API key.

    Args:
        db: Async database session.
        user: The User ORM object to update.
    """
    user.anthropic_api_key_encrypted = None
    await db.flush()
