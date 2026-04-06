"""Celery tasks for client instruction PDF generation and delivery."""
from __future__ import annotations

import asyncio

from loguru import logger

from app.celery_app import celery_app


@celery_app.task(
    name="app.tasks.client_report_tasks.generate_client_pdf",
    bind=True,
    max_retries=1,
    queue="default",
    soft_time_limit=90,
    time_limit=120,
)
def generate_client_pdf(self, report_id: str, site_id: str, blocks_config: dict) -> dict:
    """Generate client instruction PDF in subprocess-isolated WeasyPrint."""
    import uuid

    from app.database import AsyncSessionLocal
    from app.services.client_report_service import (
        generate_client_report,
        mark_report_failed,
        save_report_pdf,
    )

    async def _run():
        async with AsyncSessionLocal() as db:
            try:
                pdf_bytes = await generate_client_report(db, uuid.UUID(site_id), blocks_config)
                await save_report_pdf(db, uuid.UUID(report_id), pdf_bytes)
                await db.commit()
                logger.info("Client PDF generated", report_id=report_id, size=len(pdf_bytes))
                return {"status": "ready", "size": len(pdf_bytes)}
            except Exception as exc:
                await db.rollback()
                await mark_report_failed(db, uuid.UUID(report_id), str(exc))
                await db.commit()
                logger.error("Client PDF generation failed", report_id=report_id, error=str(exc))
                raise

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("Client PDF task failed", error=str(exc))
        raise self.retry(exc=exc, countdown=10)


@celery_app.task(
    name="app.tasks.client_report_tasks.send_client_report_email",
    bind=True,
    max_retries=3,
    queue="default",
    soft_time_limit=30,
    time_limit=45,
)
def send_client_report_email(self, report_id: str) -> dict:
    """Send completed client report PDF via email."""
    import uuid

    from sqlalchemy import select as sa_select

    from app.database import get_sync_db
    from app.models.client_report import ClientReport
    from app.models.report_schedule import ReportSchedule
    from app.models.site import Site
    from app.services.smtp_service import send_email_sync

    try:
        with get_sync_db() as db:
            report = db.execute(
                sa_select(ClientReport).where(ClientReport.id == uuid.UUID(report_id))
            ).scalar_one_or_none()
            if not report or report.pdf_data is None:
                logger.warning("Client report not found or no PDF data", report_id=report_id)
                return {"sent": False}

            site = db.execute(
                sa_select(Site).where(Site.id == report.site_id)
            ).scalar_one_or_none()
            site_name = site.name if site else "Unknown"

            schedule = db.execute(
                sa_select(ReportSchedule).where(ReportSchedule.id == 1)
            ).scalar_one_or_none()
            smtp_to = schedule.smtp_to if schedule else None

        if not smtp_to:
            logger.warning("No SMTP recipient configured for client report", report_id=report_id)
            return {"sent": False}

        body_html = (
            f"<h2>SEO-инструкции для специалиста — {site_name}</h2>"
            f"<p>Отчёт сформирован и готов к просмотру в системе.</p>"
            f"<p>Сайт: <b>{site_name}</b></p>"
        )
        sent = send_email_sync(
            to=smtp_to,
            subject=f"SEO-инструкции — {site_name}",
            body_html=body_html,
        )
        logger.info("Client report email sent", report_id=report_id, smtp_to=smtp_to, sent=sent)
        return {"sent": sent}
    except Exception as exc:
        logger.error("Client report email task failed", error=str(exc))
        raise self.retry(exc=exc, countdown=10)


@celery_app.task(
    name="app.tasks.client_report_tasks.send_client_report_telegram",
    bind=True,
    max_retries=3,
    queue="default",
    soft_time_limit=30,
    time_limit=45,
)
def send_client_report_telegram(self, report_id: str) -> dict:
    """Send Telegram notification when client report PDF is ready."""
    import uuid

    from sqlalchemy import select as sa_select

    from app.database import get_sync_db
    from app.models.client_report import ClientReport
    from app.models.site import Site
    from app.services import telegram_service

    try:
        with get_sync_db() as db:
            report = db.execute(
                sa_select(ClientReport).where(ClientReport.id == uuid.UUID(report_id))
            ).scalar_one_or_none()
            if not report:
                logger.warning("Client report not found", report_id=report_id)
                return {"sent": False}

            site = db.execute(
                sa_select(Site).where(Site.id == report.site_id)
            ).scalar_one_or_none()
            site_name = site.name if site else "Unknown"

        sent = telegram_service.send_message_sync(
            f"Клиентский отчёт сформирован: {site_name}"
        )
        logger.info("Client report Telegram sent", report_id=report_id, sent=sent)
        return {"sent": sent}
    except Exception as exc:
        logger.error("Client report Telegram task failed", error=str(exc))
        raise self.retry(exc=exc, countdown=10)
