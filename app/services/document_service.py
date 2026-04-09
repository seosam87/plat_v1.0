"""Document generation service: CRUD + 3-version cap (Phase 23).

Provides create, get, list (with type/date filters), delete, and
enforce_version_cap for GeneratedDocument records.
"""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.generated_document import GeneratedDocument
from app.models.proposal_template import TemplateType

MAX_VERSIONS = 3


async def create_document(
    db: AsyncSession,
    *,
    client_id: uuid.UUID,
    site_id: uuid.UUID | None,
    template_id: uuid.UUID,
    document_type: TemplateType,
    file_name: str = "document.pdf",
) -> GeneratedDocument:
    """Create a new document record with status='pending'."""
    doc = GeneratedDocument(
        client_id=client_id,
        site_id=site_id,
        template_id=template_id,
        document_type=document_type,
        file_name=file_name,
        status="pending",
    )
    db.add(doc)
    await db.flush()
    logger.info("Document created", doc_id=str(doc.id), client_id=str(client_id))
    return doc


async def get_document(db: AsyncSession, doc_id: uuid.UUID) -> GeneratedDocument | None:
    """Fetch a single document by ID."""
    result = await db.execute(
        select(GeneratedDocument).where(GeneratedDocument.id == doc_id)
    )
    return result.scalar_one_or_none()


async def list_documents(
    db: AsyncSession,
    client_id: uuid.UUID,
    *,
    doc_type: TemplateType | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[GeneratedDocument]:
    """List documents for a client with optional type and date filters."""
    q = select(GeneratedDocument).where(GeneratedDocument.client_id == client_id)
    if doc_type:
        q = q.where(GeneratedDocument.document_type == doc_type)
    if date_from:
        q = q.where(
            GeneratedDocument.created_at
            >= datetime(date_from.year, date_from.month, date_from.day)
        )
    if date_to:
        next_day = date_to + timedelta(days=1)
        q = q.where(
            GeneratedDocument.created_at
            < datetime(next_day.year, next_day.month, next_day.day)
        )
    q = q.order_by(GeneratedDocument.created_at.desc())
    result = await db.execute(q)
    return list(result.scalars().all())


async def delete_document(db: AsyncSession, doc_id: uuid.UUID) -> bool:
    """Delete a document. Returns False if not found or still active."""
    doc = await get_document(db, doc_id)
    if not doc:
        return False
    if doc.status in ("pending", "processing"):
        return False  # Don't delete active jobs
    await db.delete(doc)
    await db.flush()
    logger.info("Document deleted", doc_id=str(doc_id))
    return True


async def enforce_version_cap(
    db: AsyncSession, client_id: uuid.UUID, template_id: uuid.UUID
) -> int:
    """Delete oldest documents beyond MAX_VERSIONS for a client+template pair.

    Returns the number of documents deleted.
    """
    result = await db.execute(
        select(GeneratedDocument)
        .where(
            GeneratedDocument.client_id == client_id,
            GeneratedDocument.template_id == template_id,
        )
        .order_by(GeneratedDocument.created_at.asc())
    )
    docs = list(result.scalars().all())
    deleted = 0
    if len(docs) >= MAX_VERSIONS:
        # Keep only MAX_VERSIONS - 1 to make room for the new document
        to_delete = docs[: len(docs) - MAX_VERSIONS + 1]
        for d in to_delete:
            await db.delete(d)
            deleted += 1
        logger.info(
            "Version cap enforced",
            client_id=str(client_id),
            template_id=str(template_id),
            deleted=deleted,
        )
    return deleted


def build_filename(template_type_value: str, client_name: str) -> str:
    """Build download filename: {type}_{client_name}_{YYYY-MM-DD}.pdf"""
    safe_name = re.sub(r"[^\w\-]", "_", client_name)[:40]
    return f"{template_type_value}_{safe_name}_{date.today().isoformat()}.pdf"
