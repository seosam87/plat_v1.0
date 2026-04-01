"""Upload router: file upload endpoint + upload history."""
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.dependencies import get_db
from app.models.file_upload import FileType, UploadStatus
from app.models.user import User
from app.services import upload_service, keyword_service
from app.services.site_service import get_site

router = APIRouter(prefix="/uploads", tags=["uploads"])
templates = Jinja2Templates(directory="app/templates")


@router.post("/sites/{site_id}")
async def upload_file(
    site_id: uuid.UUID,
    file_type: str = Form(...),
    file: UploadFile = File(...),
    on_duplicate: str = Form("skip"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> dict:
    """Upload a file for parsing. Saves file, parses, and stores results.

    on_duplicate: skip | update | replace (default: skip)
    """
    site = await get_site(db, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    try:
        ft = FileType(file_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid file_type: {file_type}")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Empty file")

    # Save to disk + DB
    upload = await upload_service.save_upload(
        db, site_id, ft, file.filename or "unknown", file_bytes
    )

    # Parse and process
    result = await upload_service.process_upload(db, upload)

    # Save parsed keywords/groups to DB if applicable
    imported_count = 0
    if on_duplicate not in ("skip", "update", "replace"):
        on_duplicate = "skip"

    if ft in (FileType.topvisor, FileType.key_collector):
        imported_count = await _save_keywords(db, site_id, ft, result, on_duplicate)

    await db.commit()

    return {
        "upload_id": str(upload.id),
        "status": upload.status.value,
        "file_type": ft.value,
        "row_count": result.get("row_count", 0),
        "keywords_imported": imported_count,
        "result": _summarize(ft, result),
    }


@router.get("/sites/{site_id}")
async def list_uploads(
    site_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[dict]:
    uploads = await upload_service.list_uploads(db, site_id)
    return [
        {
            "id": str(u.id),
            "file_type": u.file_type.value,
            "original_name": u.original_name,
            "status": u.status.value,
            "row_count": u.row_count,
            "error_message": u.error_message,
            "uploaded_at": u.uploaded_at.isoformat() if u.uploaded_at else None,
        }
        for u in uploads
    ]


async def _save_keywords(
    db: AsyncSession,
    site_id: uuid.UUID,
    file_type: FileType,
    result: dict,
    on_duplicate: str = "skip",
) -> int:
    """Save parsed keywords (and groups for KC) into DB. Returns count."""
    keywords = result.get("keywords", [])
    if not keywords:
        return 0

    if file_type == FileType.key_collector:
        # Create groups first, then assign group_ids
        group_map: dict[str, uuid.UUID] = {}
        for kw in keywords:
            gname = kw.get("group_name")
            if gname and gname not in group_map:
                group = await keyword_service.get_or_create_group(db, site_id, gname)
                group_map[gname] = group.id

        rows = []
        for kw in keywords:
            gname = kw.get("group_name")
            rows.append({
                "phrase": kw["phrase"],
                "target_url": kw.get("url"),
                "group_id": group_map.get(gname),
                "engine": "yandex",
            })
        return await keyword_service.bulk_add_keywords(db, site_id, rows, on_duplicate=on_duplicate)

    elif file_type == FileType.topvisor:
        rows = [
            {
                "phrase": kw["phrase"],
                "frequency": kw.get("frequency"),
                "target_url": kw.get("target_url"),
            }
            for kw in keywords
        ]
        return await keyword_service.bulk_add_keywords(db, site_id, rows, on_duplicate=on_duplicate)

    return 0


def _summarize(file_type: FileType, result: dict) -> dict:
    """Build a concise summary for the API response."""
    if file_type == FileType.screaming_frog:
        return result.get("summary", {})
    elif file_type == FileType.topvisor:
        return {
            "keywords": len(result.get("keywords", [])),
            "date_columns": result.get("date_columns", []),
            "position_records": len(result.get("position_history", [])),
        }
    elif file_type == FileType.key_collector:
        return {
            "keywords": len(result.get("keywords", [])),
            "groups": result.get("groups", []),
        }
    return {}
