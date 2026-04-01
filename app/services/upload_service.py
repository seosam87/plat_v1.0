"""File upload service: store file, create FileUpload record, dispatch parsing."""
from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file_upload import FileUpload, FileType, UploadStatus

UPLOAD_DIR = Path("uploads")


async def save_upload(
    db: AsyncSession,
    site_id: uuid.UUID,
    file_type: FileType,
    original_name: str,
    file_bytes: bytes,
) -> FileUpload:
    """Save uploaded file to disk and create a FileUpload record."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Generate unique filename
    suffix = Path(original_name).suffix.lower()
    stored_name = f"{uuid.uuid4().hex}{suffix}"
    stored_path = UPLOAD_DIR / stored_name

    stored_path.write_bytes(file_bytes)

    upload = FileUpload(
        site_id=site_id,
        file_type=file_type,
        original_name=original_name,
        stored_path=str(stored_path),
        status=UploadStatus.pending,
    )
    db.add(upload)
    await db.flush()

    logger.info(
        "File uploaded",
        upload_id=str(upload.id),
        site_id=str(site_id),
        file_type=file_type.value,
        original_name=original_name,
    )
    return upload


async def process_upload(
    db: AsyncSession,
    upload: FileUpload,
) -> dict:
    """Parse the uploaded file and save results to DB.

    Returns parser output dict.
    """
    upload.status = UploadStatus.processing
    await db.flush()

    try:
        result = _dispatch_parser(upload)

        upload.status = UploadStatus.done
        upload.row_count = result.get("row_count", 0)
        await db.flush()

        return result

    except Exception as exc:
        logger.error("Upload processing failed", upload_id=str(upload.id), error=str(exc))
        upload.status = UploadStatus.failed
        upload.error_message = str(exc)[:1000]
        await db.flush()
        return {"error": str(exc), "row_count": 0}


def _dispatch_parser(upload: FileUpload) -> dict:
    """Call the appropriate parser based on file_type."""
    path = upload.stored_path

    if upload.file_type == FileType.topvisor:
        from app.parsers.topvisor_parser import parse_topvisor
        return parse_topvisor(path)

    elif upload.file_type == FileType.key_collector:
        from app.parsers.keycollector_parser import parse_keycollector
        return parse_keycollector(path)

    elif upload.file_type == FileType.screaming_frog:
        from app.parsers.screaming_frog_parser import parse_screaming_frog
        return parse_screaming_frog(path)

    else:
        raise ValueError(f"Unsupported file type: {upload.file_type}")


async def list_uploads(
    db: AsyncSession,
    site_id: uuid.UUID,
) -> list[FileUpload]:
    from sqlalchemy import select
    result = await db.execute(
        select(FileUpload)
        .where(FileUpload.site_id == site_id)
        .order_by(FileUpload.uploaded_at.desc())
    )
    return list(result.scalars().all())
