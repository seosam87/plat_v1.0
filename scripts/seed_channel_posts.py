"""Seed Telegram channel posts from docs/telegram-channel-content.md.

Creates all 13 posts as drafts in the telegram_channel_posts table.
Run: python scripts/seed_channel_posts.py

Requires: DATABASE_URL in .env (sync version).
"""
import asyncio
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, text
from app.database import AsyncSessionLocal
from app.models.channel_post import TelegramChannelPost, PostStatus


CONTENT_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs",
    "telegram-channel-content.md",
)


def parse_posts(filepath: str) -> list[dict]:
    """Parse the markdown file into individual posts."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Split by ## POST N: headers
    parts = re.split(r"^## POST \d+: ", content, flags=re.MULTILINE)
    headers = re.findall(r"^## POST \d+: (.+)$", content, flags=re.MULTILINE)

    posts = []
    for i, (title, body) in enumerate(zip(headers, parts[1:]), 1):
        # Clean up body: remove leading/trailing whitespace and separator lines
        body = body.strip()
        # Remove the trailing --- separator if present
        body = re.sub(r"\n---\s*$", "", body)
        # Remove the recommendation line at the very end of last post
        if i == 13:
            body = re.sub(
                r"\n\*Все посты готовы к публикации\..*$",
                "",
                body,
                flags=re.DOTALL,
            )

        # Convert markdown to Telegram HTML
        tg_html = md_to_telegram_html(body.strip())

        posts.append({
            "order": i,
            "title": title.strip(),
            "content": tg_html,
        })

    return posts


def md_to_telegram_html(md: str) -> str:
    """Convert markdown to Telegram-compatible HTML.

    Telegram supports: <b>, <i>, <u>, <s>, <code>, <pre>, <a href="">.
    Does NOT support: headers, lists, tables, images.
    """
    lines = md.split("\n")
    result = []

    in_code_block = False
    code_lang = ""
    code_lines = []

    for line in lines:
        # Code blocks
        if line.startswith("```"):
            if in_code_block:
                # Close code block
                code_content = "\n".join(code_lines)
                # Escape HTML inside code
                code_content = (
                    code_content.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                )
                result.append(f"<pre>{code_content}</pre>")
                in_code_block = False
                code_lines = []
            else:
                # Open code block
                in_code_block = True
                code_lang = line[3:].strip()
                code_lines = []
            continue

        if in_code_block:
            code_lines.append(line)
            continue

        # Skip table separator lines
        if re.match(r"^\|[-|: ]+\|$", line):
            continue

        # Table rows -> simple text
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            # Format as "key — value" for 2-column tables
            if len(cells) == 2:
                cells = [inline_format(c) for c in cells]
                line = f"{cells[0]} — {cells[1]}"
            else:
                line = " | ".join(inline_format(c) for c in cells)

        # Headers -> bold
        elif line.startswith("###"):
            line = f"\n<b>{inline_format(line.lstrip('#').strip())}</b>"
        elif line.startswith("##"):
            line = f"\n<b>{inline_format(line.lstrip('#').strip())}</b>"
        elif line.startswith("#"):
            line = f"\n<b>{inline_format(line.lstrip('#').strip())}</b>\n"

        # List items
        elif line.startswith("- "):
            line = f"• {inline_format(line[2:])}"
        elif re.match(r"^\d+\. ", line):
            num = re.match(r"^(\d+)\. ", line).group(1)
            line = f"{num}. {inline_format(line[len(num)+2:])}"

        # Blockquotes
        elif line.startswith("> "):
            line = f"<i>{inline_format(line[2:])}</i>"

        # Horizontal rules
        elif line.strip() == "---":
            line = "———"

        # Regular lines
        else:
            line = inline_format(line)

        result.append(line)

    return "\n".join(result).strip()


def inline_format(text: str) -> str:
    """Convert inline markdown to Telegram HTML."""
    # Inline code
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # Bold
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    # Italic (single *)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    # Links [text](url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    return text


async def seed():
    posts = parse_posts(CONTENT_FILE)
    print(f"Parsed {len(posts)} posts from {CONTENT_FILE}")

    # Get the first admin user ID
    async with AsyncSessionLocal() as db:
        row = await db.execute(
            text("SELECT id FROM users WHERE role = 'admin' LIMIT 1")
        )
        user = row.first()
        if not user:
            print("ERROR: No admin user found. Create a user first.")
            return
        user_id = user[0]
        print(f"Using admin user: {user_id}")

        # Check if posts already exist
        existing = await db.execute(
            select(TelegramChannelPost).limit(1)
        )
        if existing.scalar_one_or_none():
            print("Posts already exist. Delete them first or skip seeding.")
            return

        for p in posts:
            post = TelegramChannelPost(
                title=p["title"],
                content=p["content"],
                status=PostStatus.draft,
                created_by_id=user_id,
            )
            db.add(post)
            print(f"  + Post {p['order']}: {p['title']}")

        await db.commit()
        print(f"\nDone! {len(posts)} drafts created. Open /ui/channel/ to manage them.")


if __name__ == "__main__":
    asyncio.run(seed())
