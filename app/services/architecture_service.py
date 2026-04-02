"""Architecture service: SF import, sitemap comparison, URL tree, role detection, inlinks diff."""
from __future__ import annotations

import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urlparse

import httpx
from loguru import logger
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.architecture import PageLink, SitemapEntry
from app.models.crawl import ArchitectureRole, Page


# ---- SF Import (async) ----


async def import_sf_data(
    db: AsyncSession, site_id: uuid.UUID, file_path: str
) -> dict:
    """Import Screaming Frog data into Page model with source='sf_import'."""
    from app.parsers.screaming_frog_parser import parse_screaming_frog

    result = parse_screaming_frog(file_path)
    pages = result.get("pages", [])
    count = 0

    for p in pages:
        url = p.get("url", "")
        if not url:
            continue

        stmt = insert(Page).values(
            id=uuid.uuid4(),
            site_id=site_id,
            crawl_job_id=uuid.uuid4(),  # synthetic job ID for SF import
            url=url,
            title=p.get("title"),
            h1=p.get("h1"),
            http_status=p.get("http_status"),
            word_count=p.get("word_count"),
            inlinks_count=p.get("inlinks"),
            source="sf_import",
        )
        # On conflict by (crawl_job_id, url) — update
        # Since crawl_job_id is unique per import, this will insert new rows
        try:
            await db.execute(stmt)
            count += 1
        except Exception:
            pass  # skip duplicates

    await db.flush()
    return {"imported": count, "tab_type": result.get("tab_type", "unknown")}


# ---- Sitemap comparison ----

_SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def parse_sitemap_xml(content: str) -> list[dict]:
    """Parse sitemap.xml content. Returns [{url, lastmod}]."""
    if not content or not content.strip():
        return []

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    entries = []
    tag = root.tag.lower()

    # Sitemap index
    if "sitemapindex" in tag:
        for sitemap in root.findall("sm:sitemap", _SITEMAP_NS) or root.findall("sitemap"):
            loc = sitemap.findtext("sm:loc", namespaces=_SITEMAP_NS) or sitemap.findtext("loc")
            if loc:
                entries.append({"url": loc.strip(), "lastmod": None, "is_index": True})
        return entries

    # Regular sitemap
    for url_el in root.findall("sm:url", _SITEMAP_NS) or root.findall("url"):
        loc = url_el.findtext("sm:loc", namespaces=_SITEMAP_NS) or url_el.findtext("loc")
        lastmod = url_el.findtext("sm:lastmod", namespaces=_SITEMAP_NS) or url_el.findtext("lastmod")
        if loc:
            entries.append({"url": loc.strip(), "lastmod": lastmod})

    return entries


async def fetch_sitemap(site_url: str) -> str | None:
    """Fetch sitemap.xml from site."""
    url = site_url.rstrip("/") + "/sitemap.xml"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code == 200:
                return resp.text
    except Exception as exc:
        logger.warning("Failed to fetch sitemap", url=url, error=str(exc))
    return None


async def compare_sitemap(
    db: AsyncSession,
    site_id: uuid.UUID,
    sitemap_urls: list[dict],
) -> dict:
    """Compare sitemap URLs with crawled pages. Save SitemapEntry records."""
    # Get all crawled URLs for site
    result = await db.execute(
        select(Page.url).where(Page.site_id == site_id).distinct()
    )
    crawl_urls = {r[0] for r in result.all()}

    sitemap_url_set = {u["url"].rstrip("/") for u in sitemap_urls if not u.get("is_index")}
    crawl_url_normalized = {u.rstrip("/") for u in crawl_urls}

    orphan = crawl_url_normalized - sitemap_url_set
    missing = sitemap_url_set - crawl_url_normalized
    ok = crawl_url_normalized & sitemap_url_set

    # Build lastmod lookup
    lastmod_map = {u["url"].rstrip("/"): u.get("lastmod") for u in sitemap_urls}

    # Upsert entries
    all_urls = orphan | missing | ok
    for url in all_urls:
        if url in ok:
            status = "ok"
        elif url in orphan:
            status = "orphan"
        else:
            status = "missing"

        stmt = insert(SitemapEntry).values(
            id=uuid.uuid4(),
            site_id=site_id,
            url=url,
            in_sitemap=url in sitemap_url_set,
            in_crawl=url in crawl_url_normalized,
            status=status,
            created_at=datetime.now(timezone.utc),
        )
        stmt = stmt.on_conflict_do_update(
            constraint="uq_sitemap_entry_site_url",
            set_={
                "in_sitemap": stmt.excluded.in_sitemap,
                "in_crawl": stmt.excluded.in_crawl,
                "status": stmt.excluded.status,
            },
        )
        await db.execute(stmt)

    await db.flush()
    return {
        "total_sitemap": len(sitemap_url_set),
        "total_crawl": len(crawl_url_normalized),
        "orphan": len(orphan),
        "missing": len(missing),
        "ok": len(ok),
    }


# ---- URL Tree (pure) ----


def build_url_tree(urls: list[str]) -> dict:
    """Build a nested tree from URL path segments. D3.js-compatible format."""
    root: dict = {"name": "/", "full_url": None, "children": [], "page_count": 0}
    url_set = set()

    for url in urls:
        try:
            parsed = urlparse(url)
            path = parsed.path.strip("/")
        except Exception:
            continue

        if not path:
            root["full_url"] = url
            root["page_count"] += 1
            url_set.add("")
            continue

        segments = path.split("/")
        node = root
        for i, seg in enumerate(segments):
            found = None
            for child in node["children"]:
                if child["name"] == seg:
                    found = child
                    break
            if not found:
                partial_path = "/".join(segments[: i + 1])
                found = {
                    "name": seg,
                    "full_url": url if i == len(segments) - 1 else None,
                    "children": [],
                    "page_count": 0,
                }
                node["children"].append(found)
            if i == len(segments) - 1:
                found["full_url"] = url
            node = found

        root["page_count"] += 1

    # Compute page_count for intermediate nodes
    _compute_counts(root)
    return root


def _compute_counts(node: dict) -> int:
    if not node["children"]:
        node["page_count"] = 1 if node["full_url"] else 0
        return node["page_count"]
    total = (1 if node["full_url"] else 0)
    for child in node["children"]:
        total += _compute_counts(child)
    node["page_count"] = total
    return total


# ---- Architecture Role Detection (async) ----


async def detect_architecture_roles(
    db: AsyncSession, site_id: uuid.UUID, crawl_job_id: uuid.UUID | None = None
) -> int:
    """Auto-detect architecture roles based on page_type + URL patterns + link data."""
    q = select(Page).where(Page.site_id == site_id)
    if crawl_job_id:
        q = q.where(Page.crawl_job_id == crawl_job_id)
    result = await db.execute(q.order_by(Page.crawled_at.desc()))
    pages = result.scalars().all()

    count = 0
    for p in pages:
        role = _classify_role(p)
        if role != ArchitectureRole.unknown:
            p.architecture_role = role
            count += 1

    await db.flush()
    return count


def _classify_role(page) -> ArchitectureRole:
    """Heuristic role classification."""
    url_lower = (page.url or "").lower()
    pt = page.page_type.value if hasattr(page.page_type, "value") else str(page.page_type)
    ct = page.content_type.value if hasattr(page.content_type, "value") else str(page.content_type)
    inlinks = page.inlinks_count or 0

    # Authority pages
    if any(p in url_lower for p in ("/otzyvy", "/reviews", "/cases", "/kejsy", "/sertifikat", "/portfolio")):
        return ArchitectureRole.authority

    # Trigger pages
    if any(p in url_lower for p in ("/promo", "/akcii", "/skidki", "/sale", "/landing")):
        return ArchitectureRole.trigger

    # Pillar: landing page type with high inlinks
    if pt == "landing" and inlinks >= 5:
        return ArchitectureRole.pillar

    # Service pages
    if any(p in url_lower for p in ("/uslugi/", "/services/", "/service/")):
        # Subservice if deeper
        parts = url_lower.rstrip("/").split("/")
        service_idx = next((i for i, seg in enumerate(parts) if seg in ("uslugi", "services", "service")), -1)
        if service_idx >= 0 and len(parts) > service_idx + 2:
            return ArchitectureRole.subservice
        return ArchitectureRole.service

    if pt == "product":
        return ArchitectureRole.service

    # Article
    if pt == "article" or ct == "informational":
        # Link accelerator: informational with high inlinks
        if inlinks >= 10:
            return ArchitectureRole.link_accelerator
        return ArchitectureRole.article

    return ArchitectureRole.unknown


async def update_page_role(
    db: AsyncSession, page_id: uuid.UUID, role: str
) -> None:
    result = await db.execute(select(Page).where(Page.id == page_id))
    page = result.scalar_one_or_none()
    if page:
        page.architecture_role = role
        await db.flush()


# ---- Inlinks Diff (pure) ----


def compute_inlinks_diff(
    old_links: list[dict], new_links: list[dict]
) -> dict:
    """Compare two sets of link records. Returns added/removed."""
    old_set = {(l["source_url"], l["target_url"]) for l in old_links}
    new_set = {(l["source_url"], l["target_url"]) for l in new_links}

    added_keys = new_set - old_set
    removed_keys = old_set - new_set

    # Build lookup for anchor text
    new_lookup = {(l["source_url"], l["target_url"]): l.get("anchor_text", "") for l in new_links}
    old_lookup = {(l["source_url"], l["target_url"]): l.get("anchor_text", "") for l in old_links}

    added = [
        {"source_url": s, "target_url": t, "anchor_text": new_lookup.get((s, t), "")}
        for s, t in added_keys
    ]
    removed = [
        {"source_url": s, "target_url": t, "anchor_text": old_lookup.get((s, t), "")}
        for s, t in removed_keys
    ]

    return {
        "added": added,
        "removed": removed,
        "added_count": len(added),
        "removed_count": len(removed),
    }


def save_page_links(
    db: Session, site_id: uuid.UUID, crawl_job_id: uuid.UUID, links: list[dict]
) -> int:
    """Bulk insert PageLink records."""
    count = 0
    for l in links:
        pl = PageLink(
            site_id=site_id,
            crawl_job_id=crawl_job_id,
            source_url=l["source_url"],
            target_url=l["target_url"],
            anchor_text=l.get("anchor_text"),
        )
        db.add(pl)
        count += 1
    return count
