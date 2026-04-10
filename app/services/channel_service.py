"""Channel service — CRUD + Telegram Bot API integration for channel post management."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.channel_post import PostStatus, TelegramChannelPost

TELEGRAM_API_BASE = "https://api.telegram.org/bot{token}"


async def _tg_request(method: str, payload: dict) -> dict:
    """POST to Telegram Bot API and return the result dict."""
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN is not configured")
    base = TELEGRAM_API_BASE.format(token=token)
    url = f"{base}/{method}"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            if not data.get("ok"):
                raise ValueError(f"Telegram API error: {data.get('description', 'unknown')}")
            logger.info("Telegram API call succeeded", method=method)
            return data.get("result", {})
    except httpx.HTTPStatusError as exc:
        logger.error("Telegram API HTTP error", method=method, status=exc.response.status_code)
        raise
    except Exception as exc:
        logger.error("Telegram API call failed", method=method, error=str(exc))
        raise


async def list_posts(
    db: AsyncSession,
    status: str | None = None,
    sort: str = "created_at_desc",
    page: int = 1,
    per_page: int = 50,
) -> tuple[list[TelegramChannelPost], int]:
    """Return (posts, total_count) with optional status filter and sorting."""
    base_q = select(TelegramChannelPost)
    count_q = select(func.count(TelegramChannelPost.id))

    if status:
        try:
            status_enum = PostStatus(status)
            base_q = base_q.where(TelegramChannelPost.status == status_enum)
            count_q = count_q.where(TelegramChannelPost.status == status_enum)
        except ValueError:
            pass  # ignore invalid status filter

    total = (await db.execute(count_q)).scalar() or 0

    if sort == "scheduled_at_asc":
        base_q = base_q.order_by(TelegramChannelPost.scheduled_at.asc().nullslast())
    else:
        # Default: created_at_desc
        base_q = base_q.order_by(TelegramChannelPost.created_at.desc())

    offset = (page - 1) * per_page
    result = await db.execute(base_q.offset(offset).limit(per_page))
    posts = list(result.scalars().all())
    return posts, total


async def get_post(db: AsyncSession, post_id: int) -> TelegramChannelPost | None:
    """Get a single post by ID."""
    result = await db.execute(
        select(TelegramChannelPost).where(TelegramChannelPost.id == post_id)
    )
    return result.scalar_one_or_none()


async def create_post(
    db: AsyncSession,
    title: str,
    content: str,
    user_id: uuid.UUID,
) -> TelegramChannelPost:
    """Create a new draft post."""
    post = TelegramChannelPost(
        title=title,
        content=content,
        status=PostStatus.draft,
        created_by_id=user_id,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)
    return post


async def update_post(
    db: AsyncSession,
    post_id: int,
    title: str,
    content: str,
) -> TelegramChannelPost:
    """Update a draft or scheduled post. Raises ValueError if published."""
    post = await get_post(db, post_id)
    if post is None:
        raise ValueError(f"Post {post_id} not found")
    if post.status == PostStatus.published:
        raise ValueError("Cannot update content of a published post directly. Use edit_published().")
    post.title = title
    post.content = content
    await db.commit()
    await db.refresh(post)
    return post


async def delete_post(db: AsyncSession, post_id: int) -> None:
    """Delete a post. If published, attempt to delete the Telegram message first."""
    post = await get_post(db, post_id)
    if post is None:
        return
    if post.status == PostStatus.published and post.telegram_message_id:
        try:
            await _tg_request("deleteMessage", {
                "chat_id": settings.TELEGRAM_CHANNEL_ID,
                "message_id": post.telegram_message_id,
            })
        except Exception as exc:
            logger.warning("Failed to delete Telegram message during post deletion", error=str(exc))
    await db.delete(post)
    await db.commit()


async def publish_post(db: AsyncSession, post_id: int) -> TelegramChannelPost:
    """Publish a post to the Telegram channel immediately."""
    post = await get_post(db, post_id)
    if post is None:
        raise ValueError(f"Post {post_id} not found")
    if not settings.TELEGRAM_CHANNEL_ID:
        raise ValueError("TELEGRAM_CHANNEL_ID is not configured")

    result = await _tg_request("sendMessage", {
        "chat_id": settings.TELEGRAM_CHANNEL_ID,
        "text": post.content,
        "parse_mode": "HTML",
    })
    post.telegram_message_id = result.get("message_id")
    post.status = PostStatus.published
    post.published_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(post)
    return post


async def edit_published(
    db: AsyncSession,
    post_id: int,
    content: str,
) -> TelegramChannelPost:
    """Edit text of an already-published message via Bot API."""
    post = await get_post(db, post_id)
    if post is None:
        raise ValueError(f"Post {post_id} not found")
    if post.status != PostStatus.published or not post.telegram_message_id:
        raise ValueError("Post is not published or has no Telegram message ID")

    await _tg_request("editMessageText", {
        "chat_id": settings.TELEGRAM_CHANNEL_ID,
        "message_id": post.telegram_message_id,
        "text": content,
        "parse_mode": "HTML",
    })
    post.content = content
    await db.commit()
    await db.refresh(post)
    return post


async def toggle_pin(db: AsyncSession, post_id: int) -> TelegramChannelPost:
    """Pin or unpin a published post in the channel."""
    post = await get_post(db, post_id)
    if post is None:
        raise ValueError(f"Post {post_id} not found")
    if post.status != PostStatus.published or not post.telegram_message_id:
        raise ValueError("Post is not published or has no Telegram message ID")

    if post.pinned:
        await _tg_request("unpinChatMessage", {
            "chat_id": settings.TELEGRAM_CHANNEL_ID,
            "message_id": post.telegram_message_id,
        })
        post.pinned = False
    else:
        await _tg_request("pinChatMessage", {
            "chat_id": settings.TELEGRAM_CHANNEL_ID,
            "message_id": post.telegram_message_id,
        })
        post.pinned = True

    await db.commit()
    await db.refresh(post)
    return post


async def schedule_post(
    db: AsyncSession,
    post_id: int,
    scheduled_at: datetime,
) -> TelegramChannelPost:
    """Schedule a post for automatic publishing."""
    post = await get_post(db, post_id)
    if post is None:
        raise ValueError(f"Post {post_id} not found")
    post.status = PostStatus.scheduled
    post.scheduled_at = scheduled_at
    await db.commit()
    await db.refresh(post)
    return post
