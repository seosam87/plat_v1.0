"""Schema template engine: render JSON-LD from customizable templates, type selection, CRUD."""
from __future__ import annotations

import json
import re
import uuid

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import SchemaTemplate


# ---- Pure functions (no DB) ----

_PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")


def render_schema_template(template_json: str, page_data: dict) -> str:
    """Replace {{placeholder}} markers in a JSON-LD template with page data.

    Returns rendered JSON string. Logs warning if result is not valid JSON.
    """
    def _replace(match: re.Match) -> str:
        key = match.group(1)
        return str(page_data.get(key, ""))

    rendered = _PLACEHOLDER_RE.sub(_replace, template_json)

    try:
        parsed = json.loads(rendered)
        return json.dumps(parsed, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        logger.warning("Schema template rendered to invalid JSON", rendered=rendered[:200])
        return rendered


def generate_schema_tag(rendered_json: str) -> str:
    """Wrap rendered JSON in a <script type='application/ld+json'> tag."""
    return f'<script type="application/ld+json">{rendered_json}</script>'


def get_page_data_for_schema(
    title: str,
    url: str,
    description: str = "",
    site_name: str = "",
    author: str = "Author",
    date_published: str = "",
) -> dict:
    """Build a standard dict of page data fields for template rendering."""
    return {
        "title": title,
        "url": url,
        "description": description,
        "site_name": site_name,
        "author": author,
        "date_published": date_published,
    }


def select_schema_type_for_page(content_type: str, page_type: str) -> str:
    """Decide which schema.org type to use based on content_type and page_type."""
    if content_type == "informational":
        return "Article"
    if content_type == "commercial":
        if page_type == "product":
            return "Product"
        if page_type == "landing":
            return "Service"
        if page_type == "category":
            return "LocalBusiness"
        return "Service"
    return "Article"


# ---- Async DB functions ----


async def get_template(
    db: AsyncSession, site_id: uuid.UUID | None, schema_type: str
) -> SchemaTemplate | None:
    """Get the most specific template for a site+type.

    Priority: site-specific > system default.
    """
    if site_id is not None:
        result = await db.execute(
            select(SchemaTemplate).where(
                SchemaTemplate.site_id == site_id,
                SchemaTemplate.schema_type == schema_type,
            )
        )
        tpl = result.scalar_one_or_none()
        if tpl:
            return tpl

    result = await db.execute(
        select(SchemaTemplate).where(
            SchemaTemplate.site_id == None,  # noqa: E711
            SchemaTemplate.schema_type == schema_type,
            SchemaTemplate.is_default == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def get_all_templates(
    db: AsyncSession, site_id: uuid.UUID | None = None
) -> list[SchemaTemplate]:
    """Get all templates: defaults + site-specific. Order by schema_type."""
    q = select(SchemaTemplate)
    if site_id is not None:
        q = q.where(
            (SchemaTemplate.site_id == site_id)
            | (SchemaTemplate.site_id == None)  # noqa: E711
        )
    else:
        q = q.where(SchemaTemplate.site_id == None)  # noqa: E711
    q = q.order_by(SchemaTemplate.schema_type)
    result = await db.execute(q)
    return list(result.scalars().all())


async def create_site_template(
    db: AsyncSession,
    site_id: uuid.UUID,
    schema_type: str,
    name: str,
    template_json: str,
) -> SchemaTemplate:
    """Create or update a site-specific template."""
    result = await db.execute(
        select(SchemaTemplate).where(
            SchemaTemplate.site_id == site_id,
            SchemaTemplate.schema_type == schema_type,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.name = name
        existing.template_json = template_json
        await db.flush()
        return existing

    tpl = SchemaTemplate(
        site_id=site_id,
        schema_type=schema_type,
        name=name,
        template_json=template_json,
        is_default=False,
    )
    db.add(tpl)
    await db.flush()
    return tpl


async def delete_site_template(db: AsyncSession, template_id: uuid.UUID) -> bool:
    """Delete a site-specific template. Refuses to delete system defaults."""
    result = await db.execute(
        select(SchemaTemplate).where(SchemaTemplate.id == template_id)
    )
    tpl = result.scalar_one_or_none()
    if not tpl or tpl.is_default:
        return False
    await db.delete(tpl)
    await db.flush()
    return True


async def reset_to_default(
    db: AsyncSession, site_id: uuid.UUID, schema_type: str
) -> bool:
    """Delete site-specific override, resetting to system default."""
    result = await db.execute(
        select(SchemaTemplate).where(
            SchemaTemplate.site_id == site_id,
            SchemaTemplate.schema_type == schema_type,
            SchemaTemplate.is_default == False,  # noqa: E712
        )
    )
    tpl = result.scalar_one_or_none()
    if not tpl:
        return False
    await db.delete(tpl)
    await db.flush()
    return True


async def render_schema_for_page(
    db: AsyncSession,
    site_id: uuid.UUID,
    page_data: dict,
    content_type: str,
    page_type: str,
) -> str | None:
    """High-level: select schema type → get template → render → wrap in script tag."""
    schema_type = select_schema_type_for_page(content_type, page_type)
    tpl = await get_template(db, site_id, schema_type)
    if not tpl:
        return None
    rendered = render_schema_template(tpl.template_json, page_data)
    return generate_schema_tag(rendered)
