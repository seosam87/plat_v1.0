"""Profile router: Anthropic API key management + LLM usage stats + Telegram linking.

Endpoints:
- GET  /profile                        -- profile page with key status + usage tab
- POST /profile/anthropic-key          -- save encrypted key
- POST /profile/anthropic-key/validate -- cheap 1-token test call (HTMX partial)
- POST /profile/anthropic-key/remove   -- clear key
- GET  /profile/link-telegram          -- Telegram Login Widget callback (links account)
- POST /profile/unlink-telegram        -- removes telegram_id from user
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.config import settings
from app.dependencies import get_db
from app.models.llm_brief_job import LLMUsage
from app.models.user import User
from app.services.telegram_auth import validate_telegram_login_widget
from app.services.user_service import (
    clear_anthropic_api_key,
    get_anthropic_api_key,
    set_anthropic_api_key,
)
from app.template_engine import templates

router = APIRouter(prefix="/profile", tags=["profile"])


async def _get_usage_stats(db: AsyncSession, user: User) -> dict:
    """Return aggregated LLM usage stats for the user."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last_7d = now - timedelta(days=7)
    last_30d = now - timedelta(days=30)

    # Today
    today_res = await db.execute(
        select(
            func.count(LLMUsage.id).label("count"),
            func.coalesce(func.sum(LLMUsage.cost_usd), 0).label("cost"),
        ).where(
            LLMUsage.user_id == user.id,
            LLMUsage.created_at >= today_start,
        )
    )
    today_row = today_res.one()

    # 7 days
    w7_res = await db.execute(
        select(
            func.count(LLMUsage.id).label("count"),
            func.coalesce(func.sum(LLMUsage.cost_usd), 0).label("cost"),
        ).where(
            LLMUsage.user_id == user.id,
            LLMUsage.created_at >= last_7d,
        )
    )
    w7_row = w7_res.one()

    # 30 days
    w30_res = await db.execute(
        select(
            func.count(LLMUsage.id).label("count"),
            func.coalesce(func.sum(LLMUsage.cost_usd), 0).label("cost"),
            func.count(LLMUsage.id).filter(LLMUsage.status == "success").label("success_count"),
        ).where(
            LLMUsage.user_id == user.id,
            LLMUsage.created_at >= last_30d,
        )
    )
    w30_row = w30_res.one()

    total_30d = int(w30_row.count or 0)
    success_30d = int(w30_row.success_count or 0)
    success_rate = round(success_30d / total_30d * 100) if total_30d > 0 else 0

    # Last 20 requests
    last20_res = await db.execute(
        select(LLMUsage)
        .where(LLMUsage.user_id == user.id)
        .order_by(LLMUsage.created_at.desc())
        .limit(20)
    )
    last20 = last20_res.scalars().all()

    return {
        "today_count": int(today_row.count or 0),
        "today_cost": Decimal(str(today_row.cost or 0)),
        "w7_count": int(w7_row.count or 0),
        "w7_cost": Decimal(str(w7_row.cost or 0)),
        "w30_count": total_30d,
        "w30_cost": Decimal(str(w30_row.cost or 0)),
        "success_rate": success_rate,
        "last20": last20,
    }


# ---------------------------------------------------------------------------
# GET /profile
# ---------------------------------------------------------------------------


@router.get("/", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    msg: str = "",
    tg_linked: str = "",
    tg_unlinked: str = "",
    tg_error: str = "",
) -> HTMLResponse:
    """Render profile page with Anthropic key status + usage stats + Telegram section."""
    usage = await _get_usage_stats(db, current_user)

    # Build masked key display
    key_preview: str | None = None
    if current_user.has_anthropic_key:
        try:
            raw = await get_anthropic_api_key(db, current_user)
            if raw and len(raw) > 8:
                key_preview = raw[:8] + "…"
            else:
                key_preview = "****"
        except Exception:
            key_preview = "****"

    return templates.TemplateResponse(
        request,
        "profile/index.html",
        {
            "current_user": current_user,
            "key_preview": key_preview,
            "msg": msg,
            "tg_linked": tg_linked,
            "tg_unlinked": tg_unlinked,
            "tg_error": tg_error,
            "telegram_bot_username": settings.TELEGRAM_BOT_USERNAME,
            **usage,
        },
    )


# ---------------------------------------------------------------------------
# POST /profile/anthropic-key — save key
# ---------------------------------------------------------------------------


@router.post("/anthropic-key")
async def save_anthropic_key(
    request: Request,
    api_key: str = Form(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RedirectResponse:
    """Save Fernet-encrypted Anthropic API key for the current user."""
    await set_anthropic_api_key(db, current_user, api_key.strip())
    await db.commit()
    return RedirectResponse("/profile/?msg=saved", status_code=303)


# ---------------------------------------------------------------------------
# POST /profile/anthropic-key/validate — cheap test call (HTMX partial)
# ---------------------------------------------------------------------------


@router.post("/anthropic-key/validate", response_class=HTMLResponse)
async def validate_anthropic_key(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> HTMLResponse:
    """Make a 1-token test call to validate the stored Anthropic key.

    Returns an HTMX-friendly HTML partial (green success or red error).
    Never raises 5xx — all errors are caught and returned as HTML.
    """
    raw_key = await get_anthropic_api_key(db, current_user)
    if not raw_key:
        return HTMLResponse(
            '<div class="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">'
            "Ключ не настроен. Сохраните ключ сначала."
            "</div>"
        )

    try:
        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=raw_key)
        await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1,
            messages=[{"role": "user", "content": "hi"}],
        )
        return HTMLResponse(
            '<div class="p-3 bg-green-50 border border-green-200 rounded text-sm text-green-700 font-medium">'
            "Ключ работает"
            "</div>"
        )
    except Exception as exc:
        logger.warning("Anthropic key validation failed for user {}: {}", current_user.id, exc)
        return HTMLResponse(
            f'<div class="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">'
            f"Ошибка: {exc}"
            f"</div>"
        )


# ---------------------------------------------------------------------------
# POST /profile/anthropic-key/remove — clear key
# ---------------------------------------------------------------------------


@router.post("/anthropic-key/remove")
async def remove_anthropic_key(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RedirectResponse:
    """Remove the stored Anthropic API key for the current user."""
    await clear_anthropic_api_key(db, current_user)
    await db.commit()
    return RedirectResponse("/profile/?msg=removed", status_code=303)


# ---------------------------------------------------------------------------
# GET /profile/link-telegram — Telegram Login Widget callback
# ---------------------------------------------------------------------------


@router.get("/link-telegram")
async def link_telegram(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RedirectResponse:
    """Handle Telegram Login Widget callback and link telegram_id to user account.

    Telegram sends: id, first_name, last_name, username, photo_url, auth_date, hash
    as query parameters to this URL after the user authenticates via the widget.
    """
    params = dict(request.query_params)
    if not validate_telegram_login_widget(params, settings.TELEGRAM_BOT_TOKEN):
        logger.warning(
            "Invalid Telegram Login Widget signature for user {}", current_user.id
        )
        return RedirectResponse("/profile/?tg_error=invalid", status_code=303)

    telegram_id = params.get("id")
    if not telegram_id:
        return RedirectResponse("/profile/?tg_error=invalid", status_code=303)

    try:
        current_user.telegram_id = int(telegram_id)
        db.add(current_user)
        await db.commit()
        logger.info(
            "Linked telegram_id={} to user {}", telegram_id, current_user.id
        )
    except Exception as exc:
        logger.error(
            "Failed to link telegram_id={} to user {}: {}", telegram_id, current_user.id, exc
        )
        await db.rollback()
        return RedirectResponse("/profile/?tg_error=invalid", status_code=303)

    return RedirectResponse("/profile/?tg_linked=1", status_code=303)


# ---------------------------------------------------------------------------
# POST /profile/unlink-telegram — remove telegram_id
# ---------------------------------------------------------------------------


@router.post("/unlink-telegram")
async def unlink_telegram(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> RedirectResponse:
    """Remove Telegram account link from current user."""
    current_user.telegram_id = None
    db.add(current_user)
    await db.commit()
    logger.info("Unlinked telegram from user {}", current_user.id)
    return RedirectResponse("/profile/?tg_unlinked=1", status_code=303)
