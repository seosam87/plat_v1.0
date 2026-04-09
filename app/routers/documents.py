"""Document generator router: generate, list, download, send, regenerate, delete."""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_manager_or_above
from app.dependencies import get_db
from app.models.client import Client
from app.models.generated_document import GeneratedDocument
from app.models.proposal_template import TemplateType
from app.models.site import Site
from app.models.user import User
from app.services import document_service
from app.services import template_service
from app.tasks.document_tasks import generate_document_pdf, send_document
from app.template_engine import templates

router = APIRouter(
    prefix="/ui/crm/clients/{client_id}/documents",
    tags=["documents"],
)


async def _get_client_or_404(db: AsyncSession, client_id: uuid.UUID) -> Client:
    result = await db.execute(select(Client).where(Client.id == client_id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.get("/", response_class=HTMLResponse)
async def documents_tab(
    request: Request,
    client_id: uuid.UUID,
    doc_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    """Documents tab content: generate form + filters + table."""
    client = await _get_client_or_404(db, client_id)

    # Fetch client sites for the generate form dropdown
    result = await db.execute(
        select(Site).where(Site.client_id == client_id).order_by(Site.name)
    )
    sites = list(result.scalars().all())

    # Fetch templates
    templates_list = await template_service.list_templates(db)

    # Parse filters
    parsed_type: TemplateType | None = None
    if doc_type:
        try:
            parsed_type = TemplateType(doc_type)
        except ValueError:
            pass

    parsed_date_from = None
    parsed_date_to = None
    if date_from:
        try:
            parsed_date_from = datetime.strptime(date_from, "%Y-%m-%d").date()
        except ValueError:
            pass
    if date_to:
        try:
            parsed_date_to = datetime.strptime(date_to, "%Y-%m-%d").date()
        except ValueError:
            pass

    # Fetch documents with filters
    documents = await document_service.list_documents(
        db,
        client_id,
        doc_type=parsed_type,
        date_from=parsed_date_from,
        date_to=parsed_date_to,
    )

    context = {
        "client": client,
        "sites": sites,
        "templates_list": templates_list,
        "documents": documents,
        "active_tab": "documents",
        "doc_type_filter": doc_type,
        "date_from_filter": date_from,
        "date_to_filter": date_to,
    }

    # If HTMX request, return just the tab partial
    if request.headers.get("HX-Request"):
        return templates.TemplateResponse(
            request, "crm/_documents_tab.html", context
        )

    # Full page with active tab
    return templates.TemplateResponse(
        request, "crm/detail.html", context
    )


@router.post("/generate", response_class=HTMLResponse)
async def generate_document(
    request: Request,
    client_id: uuid.UUID,
    template_id: uuid.UUID = Form(...),
    site_id: uuid.UUID = Form(...),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    """Create document record + dispatch Celery PDF generation task."""
    client = await _get_client_or_404(db, client_id)

    # Validate template
    template = await template_service.get_template(db, template_id)
    if not template:
        raise HTTPException(status_code=400, detail="Template not found")

    # Enforce version cap
    await document_service.enforce_version_cap(db, client_id, template_id)

    # Build filename
    filename = document_service.build_filename(
        template.template_type.value, client.company_name
    )

    # Create document record
    doc = await document_service.create_document(
        db,
        client_id=client_id,
        site_id=site_id,
        template_id=template_id,
        document_type=template.template_type,
        file_name=filename,
    )

    # Dispatch Celery task
    task = generate_document_pdf.delay(
        str(doc.id), str(template_id), str(client_id), str(site_id)
    )
    doc.celery_task_id = task.id
    await db.commit()

    return templates.TemplateResponse(
        request,
        "crm/documents/_gen_status.html",
        {"doc": doc, "client_id": client_id},
    )


@router.get("/{doc_id}/status", response_class=HTMLResponse)
async def document_status(
    request: Request,
    client_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    """HTMX polling endpoint for document generation status."""
    doc = await document_service.get_document(db, doc_id)
    if not doc or doc.client_id != client_id:
        raise HTTPException(status_code=404, detail="Document not found")

    response = templates.TemplateResponse(
        request,
        "crm/documents/_gen_status.html",
        {"doc": doc, "client_id": client_id},
    )

    # When ready, trigger table refresh
    if doc.status == "ready":
        response.headers["HX-Trigger"] = "refreshDocList"

    return response


@router.get("/{doc_id}/download")
async def download_document(
    client_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_manager_or_above),
) -> Response:
    """Download generated PDF document."""
    doc = await document_service.get_document(db, doc_id)
    if not doc or doc.client_id != client_id:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.status != "ready" or doc.pdf_data is None:
        raise HTTPException(status_code=400, detail="Document not ready for download")

    # RFC 5987: use filename* with UTF-8 encoding for non-ASCII filenames
    from urllib.parse import quote
    safe_name = doc.file_name.encode("ascii", "replace").decode("ascii")
    encoded_name = quote(doc.file_name)
    return Response(
        content=doc.pdf_data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=\"{safe_name}\"; filename*=UTF-8''{encoded_name}"
        },
    )


@router.post("/{doc_id}/send", response_class=HTMLResponse)
async def send_doc(
    request: Request,
    client_id: uuid.UUID,
    doc_id: uuid.UUID,
    channel: str = Form(...),
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    """Dispatch send task for a ready document via email or telegram."""
    if channel not in ("email", "telegram"):
        raise HTTPException(status_code=400, detail="Invalid channel")

    doc = await document_service.get_document(db, doc_id)
    if not doc or doc.client_id != client_id:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.status != "ready":
        raise HTTPException(status_code=400, detail="Document not ready for sending")

    client = await _get_client_or_404(db, client_id)

    if channel == "email":
        if not client.email:
            return HTMLResponse(
                content='<div style="background:#fee2e2;color:#991b1b;padding:0.75rem 1rem;border-radius:6px;font-size:0.875rem;margin-bottom:0.5rem;">Email клиента не указан. Добавьте email в карточке клиента.</div>',
                status_code=400,
            )
        recipient = client.email
    else:
        recipient = ""

    send_document.delay(str(doc.id), channel, recipient, str(client_id))

    return HTMLResponse(
        content='<div id="send-toast" style="background:#d1fae5;color:#065f46;padding:0.75rem 1rem;border-radius:6px;font-size:0.875rem;margin-bottom:0.5rem;">Документ отправляется...</div><script>setTimeout(function(){var el=document.getElementById("send-toast");if(el)el.remove();},4000)</script>',
    )


@router.post("/{doc_id}/regenerate", response_class=HTMLResponse)
async def regenerate_document(
    request: Request,
    client_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    """Create a new version of a document by regenerating from same template."""
    original = await document_service.get_document(db, doc_id)
    if not original or original.client_id != client_id:
        raise HTTPException(status_code=404, detail="Document not found")

    if not original.template_id:
        raise HTTPException(
            status_code=400, detail="Template was deleted, cannot regenerate"
        )

    template = await template_service.get_template(db, original.template_id)
    if not template:
        raise HTTPException(status_code=400, detail="Template not found")

    client = await _get_client_or_404(db, client_id)

    # Enforce version cap
    await document_service.enforce_version_cap(db, client_id, original.template_id)

    # Build filename
    filename = document_service.build_filename(
        template.template_type.value, client.company_name
    )

    # Create new document
    doc = await document_service.create_document(
        db,
        client_id=client_id,
        site_id=original.site_id,
        template_id=original.template_id,
        document_type=template.template_type,
        file_name=filename,
    )

    # Dispatch Celery task
    site_id_str = str(original.site_id) if original.site_id else None
    task = generate_document_pdf.delay(
        str(doc.id), str(original.template_id), str(client_id), site_id_str
    )
    doc.celery_task_id = task.id
    await db.commit()

    return templates.TemplateResponse(
        request,
        "crm/documents/_gen_status.html",
        {"doc": doc, "client_id": client_id},
    )


@router.post("/{doc_id}/delete", response_class=HTMLResponse)
async def delete_doc(
    request: Request,
    client_id: uuid.UUID,
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user: User = Depends(require_manager_or_above),
) -> HTMLResponse:
    """Hard delete a document."""
    deleted = await document_service.delete_document(db, doc_id)
    if not deleted:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete: document not found or has active job",
        )
    await db.commit()

    response = HTMLResponse(content="", status_code=200)
    response.headers["HX-Trigger"] = "refreshDocList"
    return response
