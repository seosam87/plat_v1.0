"""Change monitoring service: detect changes, match rules, dispatch alerts."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.change_monitoring import (
    AlertSeverity,
    ChangeAlert,
    ChangeAlertRule,
    ChangeType,
)


# ---- Pure detection ----


def detect_changes(
    page_url: str,
    old_snap: dict | None,
    new_snap: dict,
    http_status: int,
) -> list[dict]:
    """Detect SEO-critical changes between old and new page snapshots.

    Returns list of {change_type: str, details: str}.
    """
    if old_snap is None:
        return [{"change_type": "new_page", "details": ""}]

    changes: list[dict] = []

    # 404
    old_status = old_snap.get("http_status", 200)
    if http_status == 404 and old_status != 404:
        changes.append({"change_type": "page_404", "details": f"HTTP {old_status} → 404"})

    # noindex added
    if not old_snap.get("has_noindex", False) and new_snap.get("has_noindex", False):
        changes.append({"change_type": "noindex_added", "details": ""})

    # schema removed
    if old_snap.get("has_schema", False) and not new_snap.get("has_schema", False):
        changes.append({"change_type": "schema_removed", "details": ""})

    # title changed
    old_title = old_snap.get("title", "")
    new_title = new_snap.get("title", "")
    if old_title and new_title and old_title != new_title:
        changes.append({
            "change_type": "title_changed",
            "details": f"{old_title[:80]} → {new_title[:80]}",
        })

    # H1 changed
    old_h1 = old_snap.get("h1", "")
    new_h1 = new_snap.get("h1", "")
    if old_h1 and new_h1 and old_h1 != new_h1:
        changes.append({
            "change_type": "h1_changed",
            "details": f"{old_h1[:80]} → {new_h1[:80]}",
        })

    # canonical changed
    old_can = old_snap.get("canonical_url", "")
    new_can = new_snap.get("canonical_url", "")
    if old_can != new_can and (old_can or new_can):
        changes.append({
            "change_type": "canonical_changed",
            "details": f"{old_can[:100]} → {new_can[:100]}",
        })

    # meta description changed
    old_meta = old_snap.get("meta_description", "")
    new_meta = new_snap.get("meta_description", "")
    if old_meta and new_meta and old_meta != new_meta:
        changes.append({
            "change_type": "meta_description_changed",
            "details": f"{old_meta[:80]} → {new_meta[:80]}",
        })

    # content changed
    old_content = old_snap.get("content_preview", "")
    new_content = new_snap.get("content_preview", "")
    if old_content != new_content and (old_content or new_content):
        changes.append({"change_type": "content_changed", "details": ""})

    return changes


# ---- DB functions (sync for Celery) ----


def get_alert_rules_sync(db: Session) -> dict[str, dict]:
    """Return {change_type_value: {"severity": str, "is_active": bool}}."""
    rules = db.execute(select(ChangeAlertRule)).scalars().all()
    return {
        r.change_type.value: {
            "severity": r.severity.value,
            "is_active": r.is_active,
        }
        for r in rules
    }


def save_change_alerts(
    db: Session,
    site_id: uuid.UUID,
    crawl_job_id: uuid.UUID,
    changes: list[dict],
    rules: dict[str, dict],
) -> list[ChangeAlert]:
    """Save detected changes as ChangeAlert records. Skip inactive rules."""
    created = []
    for ch in changes:
        ct = ch["change_type"]
        rule = rules.get(ct)
        if not rule or not rule["is_active"]:
            continue

        alert = ChangeAlert(
            site_id=site_id,
            crawl_job_id=crawl_job_id,
            change_type=ct,
            severity=rule["severity"],
            page_url=ch.get("page_url", ""),
            details=ch.get("details", ""),
        )
        db.add(alert)
        created.append(alert)

    return created


def mark_alerts_sent(db: Session, alert_ids: list[uuid.UUID]) -> None:
    """Set sent_at for given alerts."""
    now = datetime.now(timezone.utc)
    for aid in alert_ids:
        alert = db.get(ChangeAlert, aid)
        if alert:
            alert.sent_at = now


# ---- Telegram dispatch ----


def dispatch_immediate_alerts(
    db: Session, site_name: str, alerts: list[ChangeAlert]
) -> int:
    """Send Telegram alerts for error-severity changes. Returns count sent."""
    from app.services.telegram_service import format_change_alert, send_message_sync

    sent = 0
    error_alerts = [a for a in alerts if a.severity == AlertSeverity.error.value or a.severity == AlertSeverity.error]
    for alert in error_alerts:
        ct = alert.change_type.value if hasattr(alert.change_type, "value") else alert.change_type
        msg = format_change_alert(site_name, ct, alert.page_url, alert.details or "")
        if send_message_sync(msg):
            sent += 1
        alert.sent_at = datetime.now(timezone.utc)

    return sent


# ---- Orchestrator ----


def process_crawl_changes(
    db: Session,
    site_id: uuid.UUID,
    site_name: str,
    crawl_job_id: uuid.UUID,
) -> dict:
    """Detect changes from crawl, save alerts, dispatch immediate notifications.

    Called after crawl completes, inside sync DB session.
    """
    from app.models.crawl import Page, PageSnapshot
    from app.services.diff_service import build_snapshot

    # Get current crawl pages
    current_pages = db.execute(
        select(Page).where(Page.crawl_job_id == crawl_job_id)
    ).scalars().all()

    if not current_pages:
        return {"total_changes": 0, "alerts_sent": 0}

    # Get alert rules
    rules = get_alert_rules_sync(db)

    all_changes: list[dict] = []
    for page in current_pages:
        new_snap = build_snapshot(page)

        # Find previous version of this page (different crawl job)
        prev_page = db.execute(
            select(Page).where(
                Page.site_id == site_id,
                Page.url == page.url,
                Page.id != page.id,
            ).order_by(Page.crawled_at.desc()).limit(1)
        ).scalar_one_or_none()

        old_snap = build_snapshot(prev_page) if prev_page else None

        changes = detect_changes(
            page.url, old_snap, new_snap, page.http_status or 200
        )
        for ch in changes:
            ch["page_url"] = page.url
        all_changes.extend(changes)

    # Save alerts
    alerts = save_change_alerts(db, site_id, crawl_job_id, all_changes, rules)

    # Dispatch immediate (error) alerts
    sent = dispatch_immediate_alerts(db, site_name, alerts)

    logger.info(
        "Change monitoring processed",
        site=site_name,
        changes=len(all_changes),
        alerts=len(alerts),
        sent=sent,
    )

    return {"total_changes": len(all_changes), "alerts_sent": sent}
