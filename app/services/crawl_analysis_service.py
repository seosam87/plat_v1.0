"""Crawl analysis service: duplicate detection, orphan pages, canonical issues."""
from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def find_duplicate_titles(
    db: AsyncSession,
    site_id: uuid.UUID,
    crawl_job_id: uuid.UUID,
) -> list[dict]:
    """Find pages with duplicate titles within a crawl job.

    Returns list of dicts: {title, urls: [url, ...], count}.
    """
    query = text("""
        SELECT title, array_agg(url) AS urls, COUNT(*) AS cnt
        FROM pages
        WHERE site_id = :site_id
          AND crawl_job_id = :crawl_job_id
          AND title IS NOT NULL AND title != ''
        GROUP BY title
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
    """)
    result = await db.execute(query, {"site_id": site_id, "crawl_job_id": crawl_job_id})
    return [
        {"title": r.title, "urls": list(r.urls), "count": r.cnt}
        for r in result
    ]


async def find_duplicate_h1(
    db: AsyncSession,
    site_id: uuid.UUID,
    crawl_job_id: uuid.UUID,
) -> list[dict]:
    """Find pages with duplicate H1 headings within a crawl job.

    Returns list of dicts: {h1, urls: [url, ...], count}.
    """
    query = text("""
        SELECT h1, array_agg(url) AS urls, COUNT(*) AS cnt
        FROM pages
        WHERE site_id = :site_id
          AND crawl_job_id = :crawl_job_id
          AND h1 IS NOT NULL AND h1 != ''
        GROUP BY h1
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
    """)
    result = await db.execute(query, {"site_id": site_id, "crawl_job_id": crawl_job_id})
    return [
        {"h1": r.h1, "urls": list(r.urls), "count": r.cnt}
        for r in result
    ]


async def find_orphan_pages(
    db: AsyncSession,
    site_id: uuid.UUID,
    crawl_job_id: uuid.UUID,
) -> list[dict]:
    """Find pages with zero inbound internal links (orphan pages).

    These pages exist in the crawl but no other crawled page links to them.
    Returns list of dicts: {url, title, page_type, inlinks_count}.
    """
    query = text("""
        SELECT url, title, page_type, inlinks_count
        FROM pages
        WHERE site_id = :site_id
          AND crawl_job_id = :crawl_job_id
          AND (inlinks_count IS NULL OR inlinks_count = 0)
          AND depth > 0
        ORDER BY url
    """)
    result = await db.execute(query, {"site_id": site_id, "crawl_job_id": crawl_job_id})
    return [
        {
            "url": r.url,
            "title": r.title,
            "page_type": r.page_type,
            "inlinks_count": r.inlinks_count or 0,
        }
        for r in result
    ]


async def find_canonical_issues(
    db: AsyncSession,
    site_id: uuid.UUID,
    crawl_job_id: uuid.UUID,
) -> list[dict]:
    """Find pages where canonical URL differs from the page URL.

    Returns list of dicts: {url, canonical_url, title}.
    """
    query = text("""
        SELECT url, canonical_url, title
        FROM pages
        WHERE site_id = :site_id
          AND crawl_job_id = :crawl_job_id
          AND canonical_url IS NOT NULL
          AND canonical_url != ''
          AND canonical_url != url
        ORDER BY url
    """)
    result = await db.execute(query, {"site_id": site_id, "crawl_job_id": crawl_job_id})
    return [
        {"url": r.url, "canonical_url": r.canonical_url, "title": r.title}
        for r in result
    ]


async def get_seo_completeness(
    db: AsyncSession,
    site_id: uuid.UUID,
    crawl_job_id: uuid.UUID,
) -> dict:
    """SEO field completeness summary for a crawl job.

    Returns dict with counts: total, with_title, with_h1, with_meta,
    with_schema, with_toc, with_noindex, with_canonical.
    """
    query = text("""
        SELECT
            COUNT(*) AS total,
            COUNT(*) FILTER (WHERE title IS NOT NULL AND title != '') AS with_title,
            COUNT(*) FILTER (WHERE h1 IS NOT NULL AND h1 != '') AS with_h1,
            COUNT(*) FILTER (WHERE meta_description IS NOT NULL AND meta_description != '') AS with_meta,
            COUNT(*) FILTER (WHERE has_schema = true) AS with_schema,
            COUNT(*) FILTER (WHERE has_toc = true) AS with_toc,
            COUNT(*) FILTER (WHERE has_noindex = true) AS with_noindex,
            COUNT(*) FILTER (WHERE canonical_url IS NOT NULL AND canonical_url != '') AS with_canonical
        FROM pages
        WHERE site_id = :site_id AND crawl_job_id = :crawl_job_id
    """)
    result = await db.execute(query, {"site_id": site_id, "crawl_job_id": crawl_job_id})
    row = result.mappings().one()
    return dict(row)
