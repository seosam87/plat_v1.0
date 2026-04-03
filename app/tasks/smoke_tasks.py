"""Celery task: run UI smoke test and send results to Telegram."""
from __future__ import annotations

import asyncio

from loguru import logger

from app.celery_app import celery_app


@celery_app.task(
    name="app.tasks.smoke_tasks.run_ui_smoke_test",
    bind=True,
    max_retries=1,
    queue="default",
    soft_time_limit=120,
    time_limit=180,
)
def run_ui_smoke_test(self, base_url: str | None = None) -> dict:
    """Run the UI smoke test and send a Telegram summary.

    Args:
        base_url: If provided, test against a live server. If None, use in-process mode.

    Returns:
        dict with keys: total (int), errors (int), ok (bool)
    """
    from app.services.telegram_service import is_configured, send_message_sync
    from tests.smoke_test import run_smoke_test

    logger.info("UI smoke test started", base_url=base_url)

    try:
        results = asyncio.run(run_smoke_test(base_url=base_url))
    except Exception as exc:
        logger.error("Smoke test runner failed", error=str(exc))
        if is_configured():
            send_message_sync(f"<b>UI Smoke Test FAILED</b>\n\nRunner error: {exc}")
        raise self.retry(exc=exc, countdown=10)

    total = len(results)
    errors = [r for r in results if not r["ok"] and not r.get("skipped")]
    error_count = len(errors)
    ok = error_count == 0

    # Format Telegram message
    if ok:
        msg = (
            f"<b>UI Smoke Test PASSED</b>\n"
            f"{total} routes checked — all OK."
        )
    else:
        error_lines = "\n".join(
            f"• {r['url']} → <b>{r['status']}</b>"
            for r in errors[:20]  # cap at 20 to avoid Telegram message limit
        )
        msg = (
            f"<b>UI Smoke Test FAILED</b>\n"
            f"{total} routes checked. <b>{error_count} errors:</b>\n\n"
            f"{error_lines}"
        )
        if error_count > 20:
            msg += f"\n... and {error_count - 20} more."

    if is_configured():
        send_message_sync(msg)
    else:
        logger.info(
            "Telegram not configured; smoke test result logged only",
            ok=ok,
            errors=error_count,
        )

    logger.info("UI smoke test complete", total=total, errors=error_count, ok=ok)
    return {"total": total, "errors": error_count, "ok": ok}
