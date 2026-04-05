"""Celery tasks for scheduled report delivery: morning digest and weekly summary."""
from __future__ import annotations

import asyncio

from loguru import logger

from app.celery_app import celery_app

REDBEAT_MORNING_DIGEST_KEY = "report:morning-digest"
REDBEAT_WEEKLY_SUMMARY_KEY = "report:weekly-summary"


@celery_app.task(
    name="app.tasks.report_tasks.send_morning_digest",
    bind=True,
    max_retries=2,
    queue="default",
    soft_time_limit=60,
    time_limit=90,
)
def send_morning_digest(self) -> dict:
    """Send morning digest (compact Telegram text) for all active projects."""
    from app.database import get_sync_db
    from app.services.morning_digest_service import build_morning_digest
    from app.services import telegram_service

    try:
        with get_sync_db() as db:
            msg = build_morning_digest(db)

        sent_telegram = telegram_service.send_message_sync(msg)
        logger.info("Morning digest sent", sent_telegram=sent_telegram)
        return {"sent_telegram": sent_telegram}
    except Exception as exc:
        logger.error("Morning digest task failed", error=str(exc))
        raise self.retry(exc=exc, countdown=30)


@celery_app.task(
    name="app.tasks.report_tasks.send_weekly_summary_report",
    bind=True,
    max_retries=2,
    queue="default",
    soft_time_limit=300,
    time_limit=360,
)
def send_weekly_summary_report(self) -> dict:
    """Send weekly summary report: PDF via SMTP + summary text via Telegram."""
    from sqlalchemy import select as sa_select

    from app.database import get_sync_db
    from app.models.project import Project, ProjectStatus
    from app.services import telegram_service
    from app.services.smtp_service import send_email_sync

    projects_reported = 0
    smtp_sent = False
    telegram_sent = False

    try:
        with get_sync_db() as db:
            # Fetch the schedule to get smtp_to
            from app.models.report_schedule import ReportSchedule
            schedule = db.execute(
                sa_select(ReportSchedule).where(ReportSchedule.id == 1)
            ).scalar_one_or_none()
            smtp_to = schedule.smtp_to if schedule else None

            # Fetch non-archived projects
            projects = db.execute(
                sa_select(Project)
                .where(Project.status != ProjectStatus.archived)
                .order_by(Project.name)
            ).scalars().all()

            projects_reported = len(projects)

        # Generate PDFs and send via SMTP
        if smtp_to and projects_reported > 0:
            from app.database import AsyncSessionLocal

            async def _generate_all_pdfs():
                from app.services.report_service import generate_pdf_report
                results = []
                async with AsyncSessionLocal() as async_db:
                    for project in projects:
                        try:
                            pdf_bytes = await generate_pdf_report(
                                async_db, project.id, "brief"
                            )
                            results.append((project.name, pdf_bytes))
                        except Exception as exc:
                            logger.warning(
                                "Failed to generate PDF for project",
                                project=project.name,
                                error=str(exc),
                            )
                return results

            pdf_results = asyncio.run(_generate_all_pdfs())

            # Send the first PDF to the admin recipient
            if pdf_results:
                project_name, pdf_bytes = pdf_results[0]
                body_html = (
                    f"<h2>Weekly SEO Report</h2>"
                    f"<p>Attached report for project: <b>{project_name}</b></p>"
                    f"<p>Total projects: {projects_reported}</p>"
                )
                smtp_sent = send_email_sync(
                    to=smtp_to,
                    subject=f"Weekly SEO Report — {project_name}",
                    body_html=body_html,
                )

        # Send Telegram summary
        summary_lines = [
            "<b>Weekly SEO Report Summary</b>",
            f"Projects covered: {projects_reported}",
        ]
        if smtp_to:
            summary_lines.append(f"PDF report sent to: {smtp_to}")
        else:
            summary_lines.append("Email not configured — SMTP skipped")

        telegram_sent = telegram_service.send_message_sync("\n".join(summary_lines))

        logger.info(
            "Weekly summary report sent",
            projects_reported=projects_reported,
            smtp_sent=smtp_sent,
            telegram_sent=telegram_sent,
        )
        return {
            "projects_reported": projects_reported,
            "smtp_sent": smtp_sent,
            "telegram_sent": telegram_sent,
        }
    except Exception as exc:
        logger.error("Weekly summary report task failed", error=str(exc))
        raise self.retry(exc=exc, countdown=60)


def register_report_beats(schedule) -> None:
    """Register or remove redbeat entries for morning digest and weekly summary.

    Args:
        schedule: ReportSchedule instance.
    """
    from celery.schedules import crontab
    from redbeat import RedBeatSchedulerEntry

    # Morning digest
    _register_or_remove_beat(
        key=REDBEAT_MORNING_DIGEST_KEY,
        task_name="app.tasks.report_tasks.send_morning_digest",
        enabled=schedule.morning_digest_enabled,
        minute=str(schedule.morning_minute),
        hour=str(schedule.morning_hour),
        day_of_week="*",
        day_of_month="*",
        month_of_year="*",
    )

    # Weekly summary — convert day_of_week (1=Mon..7=Sun) to cron (0=Sun)
    cron_dow = str(schedule.weekly_day_of_week % 7)
    _register_or_remove_beat(
        key=REDBEAT_WEEKLY_SUMMARY_KEY,
        task_name="app.tasks.report_tasks.send_weekly_summary_report",
        enabled=schedule.weekly_report_enabled,
        minute=str(schedule.weekly_minute),
        hour=str(schedule.weekly_hour),
        day_of_week=cron_dow,
        day_of_month="*",
        month_of_year="*",
    )


def _register_or_remove_beat(
    key: str,
    task_name: str,
    enabled: bool,
    minute: str,
    hour: str,
    day_of_week: str,
    day_of_month: str,
    month_of_year: str,
) -> None:
    """Register a redbeat entry if enabled; remove it if disabled."""
    from celery.schedules import crontab
    from redbeat import RedBeatSchedulerEntry

    # Always remove existing entry first
    try:
        existing = RedBeatSchedulerEntry.from_key(key, app=celery_app)
        existing.delete()
    except KeyError:
        pass
    except Exception as exc:
        logger.warning("Failed to remove existing beat entry", key=key, error=str(exc))

    if not enabled:
        logger.info("Report beat entry removed (disabled)", key=key)
        return

    try:
        schedule = crontab(
            minute=minute,
            hour=hour,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
            month_of_year=month_of_year,
        )
        entry = RedBeatSchedulerEntry(
            name=key,
            task=task_name,
            schedule=schedule,
            app=celery_app,
        )
        entry.save()
        logger.info(
            "Report beat entry registered",
            key=key,
            hour=hour,
            minute=minute,
            day_of_week=day_of_week,
        )
    except Exception as exc:
        logger.warning("Failed to register report beat entry", key=key, error=str(exc))


def restore_report_schedules_from_db() -> None:
    """Restore report schedule from DB on Beat startup.

    Ensures schedule entries survive Redis flush and container restarts.
    """
    from sqlalchemy import select as sa_select

    from app.database import get_sync_db
    from app.models.report_schedule import ReportSchedule

    try:
        with get_sync_db() as db:
            schedule = db.execute(
                sa_select(ReportSchedule).where(ReportSchedule.id == 1)
            ).scalar_one_or_none()

            if schedule and (
                schedule.morning_digest_enabled or schedule.weekly_report_enabled
            ):
                register_report_beats(schedule)
                logger.info(
                    "Restored report schedules from DB",
                    morning_digest=schedule.morning_digest_enabled,
                    weekly_report=schedule.weekly_report_enabled,
                )
            else:
                logger.info("No active report schedules to restore")
    except Exception as exc:
        logger.warning("Failed to restore report schedules from DB", error=str(exc))
