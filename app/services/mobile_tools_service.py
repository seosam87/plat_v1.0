"""Mobile tools helpers: input parsing (textarea + file upload) and job lookup.

Per D-11: textarea and file upload are both available; if both provided —
error 'Используйте одно из двух: текст или файл'.
"""
from __future__ import annotations

import io
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, UploadFile
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class ToolInputResult:
    lines: list[str]
    count: int


async def parse_tool_input(
    raw_text: str,
    upload: UploadFile | None,
    limit: int,
) -> ToolInputResult:
    """Parse textarea OR file upload into a list of trimmed non-empty lines.

    D-11 rules:
    - If both `raw_text` and `upload` are non-empty → raise 422 'Используйте одно из двух'
    - If neither → raise 422 'Список не может быть пустым'
    - If count > limit → raise 422 'Превышен лимит: {limit} строк'
    - File .xlsx → openpyxl reads column A
    - File .txt (or any non-xlsx) → splitlines() on decoded bytes
    """
    has_text = bool(raw_text and raw_text.strip())
    has_file = upload is not None and (upload.filename or "").strip() != ""

    if has_text and has_file:
        raise HTTPException(
            status_code=422,
            detail="Используйте одно из двух: текст или файл",
        )
    if not has_text and not has_file:
        raise HTTPException(status_code=422, detail="Список не может быть пустым")

    if has_text:
        lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    else:
        content = await upload.read()
        filename = (upload.filename or "").lower()
        if filename.endswith(".xlsx"):
            lines = _parse_xlsx(content)
        else:
            try:
                decoded = content.decode("utf-8", errors="replace")
            except Exception as exc:
                raise HTTPException(status_code=422, detail="Не удалось прочитать файл") from exc
            lines = [ln.strip() for ln in decoded.splitlines() if ln.strip()]

    if not lines:
        raise HTTPException(status_code=422, detail="Список не может быть пустым")
    if len(lines) > limit:
        raise HTTPException(status_code=422, detail=f"Превышен лимит: {limit} строк")

    return ToolInputResult(lines=lines, count=len(lines))


def _parse_xlsx(content: bytes) -> list[str]:
    """Read column A from first worksheet. Skip header if it's non-data-ish."""
    import openpyxl
    try:
        wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Не удалось прочитать XLSX") from exc
    ws = wb.active
    result: list[str] = []
    for row in ws.iter_rows(values_only=True):
        if not row:
            continue
        cell = row[0]
        if cell is None:
            continue
        s = str(cell).strip()
        if s:
            result.append(s)
    wb.close()
    return result


async def get_job_for_user(
    db: AsyncSession,
    job_model: type,
    job_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Any | None:
    """Return job instance if it exists and belongs to user, else None."""
    stmt = select(job_model).where(job_model.id == job_id, job_model.user_id == user_id)
    result = await db.execute(stmt)
    return result.scalars().first()
