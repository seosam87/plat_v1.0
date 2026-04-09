"""Celery tasks for document PDF generation and delivery (Phase 23).

Task A: generate_document_pdf — renders template variables + HTML via subprocess PDF
Task B: send_document — dispatches via Telegram text or SMTP with attachment
"""
from __future__ import annotations

import asyncio

from loguru import logger

from app.celery_app import celery_app


def _run_async(coro):
    """Run an async coroutine from a sync Celery task, avoiding event loop conflicts."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Celery worker already has a loop — create a new one in a thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@celery_app.task(
    name="app.tasks.document_tasks.generate_document_pdf",
    bind=True,
    max_retries=3,
    queue="default",
    soft_time_limit=120,
    time_limit=150,
)
def generate_document_pdf(
    self,
    document_id: str,
    template_id: str,
    client_id: str,
    site_id: str | None,
) -> dict:
    """Generate PDF from template + resolved variables via subprocess WeasyPrint."""
    import uuid

    from app.database import AsyncSessionLocal
    from app.services.document_service import build_filename
    from app.services.subprocess_pdf import render_pdf_in_subprocess
    from app.services.template_service import get_template
    from app.services.template_variable_resolver import (
        render_template_preview,
        resolve_template_variables,
    )

    async def _run() -> dict:
        async with AsyncSessionLocal() as db:
            try:
                # 1. Mark as processing
                from app.models.generated_document import GeneratedDocument
                from sqlalchemy import select

                result = await db.execute(
                    select(GeneratedDocument).where(
                        GeneratedDocument.id == uuid.UUID(document_id)
                    )
                )
                doc = result.scalar_one_or_none()
                if not doc:
                    raise ValueError(f"Document {document_id} not found")

                doc.status = "processing"
                doc.celery_task_id = self.request.id
                await db.commit()

                # 2. Fetch template
                template = await get_template(db, uuid.UUID(template_id))
                if not template:
                    raise ValueError(f"Template {template_id} not found")

                # 3. Resolve variables
                variables = await resolve_template_variables(
                    db,
                    uuid.UUID(client_id),
                    uuid.UUID(site_id) if site_id else None,
                )

                # 4. Render HTML
                html_string = render_template_preview(template.body, variables)

                # 5. Generate PDF via subprocess (NOT direct weasyprint)
                pdf_bytes = render_pdf_in_subprocess(html_string)

                # 6. Build filename
                client_name = variables.get("client", {}).get("name", "client")
                filename = build_filename(template.template_type.value, client_name)

                # 7. Update document
                doc.pdf_data = pdf_bytes
                doc.status = "ready"
                doc.file_name = filename
                await db.commit()

                logger.info(
                    "Document PDF generated",
                    document_id=document_id,
                    size=len(pdf_bytes),
                    filename=filename,
                )
                return {"status": "ready", "size": len(pdf_bytes)}

            except Exception as exc:
                await db.rollback()
                # Mark as failed
                try:
                    result = await db.execute(
                        select(GeneratedDocument).where(
                            GeneratedDocument.id == uuid.UUID(document_id)
                        )
                    )
                    doc = result.scalar_one_or_none()
                    if doc:
                        doc.status = "failed"
                        doc.error_message = str(exc)[:500]
                        await db.commit()
                except Exception:
                    logger.error(
                        "Failed to mark document as failed",
                        document_id=document_id,
                    )
                raise

    try:
        return _run_async(_run())
    except Exception as exc:
        logger.error(
            "Document PDF task failed",
            document_id=document_id,
            error=str(exc),
        )
        raise self.retry(exc=exc, countdown=15)


@celery_app.task(
    name="app.tasks.document_tasks.send_document",
    bind=True,
    max_retries=3,
    queue="default",
    soft_time_limit=60,
    time_limit=90,
)
def send_document(
    self,
    document_id: str,
    channel: str,
    recipient: str,
    client_id: str,
) -> dict:
    """Send generated document via email (with attachment) or Telegram (text link).

    channel: "email" or "telegram"
    recipient: email address (for email) or ignored (for telegram, uses configured chat)
    """
    import uuid

    from sqlalchemy import select as sa_select

    from app.database import get_sync_db
    from app.models.generated_document import GeneratedDocument

    try:
        with get_sync_db() as db:
            doc = db.execute(
                sa_select(GeneratedDocument).where(
                    GeneratedDocument.id == uuid.UUID(document_id)
                )
            ).scalar_one_or_none()

            if not doc or doc.status != "ready" or doc.pdf_data is None:
                logger.warning(
                    "Document not ready for sending",
                    document_id=document_id,
                    status=doc.status if doc else "not_found",
                )
                return {"status": "skipped", "reason": "document_not_ready"}

            file_name = doc.file_name
            pdf_data = doc.pdf_data

        if channel == "email":
            from app.services.smtp_service import send_email_with_attachment_sync

            sent = send_email_with_attachment_sync(
                to=recipient,
                subject=f"Документ: {file_name}",
                body_html="<p>Документ сформирован в SEO-платформе.</p>",
                attachment_bytes=pdf_data,
                attachment_filename=file_name,
            )
            logger.info(
                "Document sent via email",
                document_id=document_id,
                recipient=recipient,
                sent=sent,
            )
            return {"status": "sent" if sent else "failed", "channel": "email"}

        elif channel == "telegram":
            from app.services import telegram_service

            sent = telegram_service.send_message_sync(
                f"Документ {file_name} готов. "
                f"Скачайте в платформе: /ui/crm/clients/{client_id}/documents"
            )
            logger.info(
                "Document notification sent via Telegram",
                document_id=document_id,
                sent=sent,
            )
            return {"status": "sent" if sent else "failed", "channel": "telegram"}

        else:
            logger.warning("Unknown delivery channel", channel=channel)
            return {"status": "failed", "reason": f"unknown_channel:{channel}"}

    except Exception as exc:
        logger.error(
            "Document send task failed",
            document_id=document_id,
            channel=channel,
            error=str(exc),
        )
        raise self.retry(exc=exc, countdown=10)
