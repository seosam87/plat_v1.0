import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog


async def log_action(
    db: AsyncSession,
    action: str,
    user_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    detail: dict | None = None,
) -> None:
    """Write an audit log entry in the current transaction.
    Does not commit — the caller's session commit persists the entry.
    If the calling operation rolls back, this entry rolls back too.
    """
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        detail_json=detail,
    )
    db.add(entry)
