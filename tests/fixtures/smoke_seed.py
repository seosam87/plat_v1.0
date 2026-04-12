"""Smoke seed fixture for UI smoke crawler (Phase 15.1).

Per CONTEXT D-01 and RESEARCH Pattern 2 + "Critical detail" SAVEPOINT strategy:
session-scoped, ORM-based deterministic seed bound to an OUTER connection+
transaction so each request can join via its own savepoint.

Exports:
- SMOKE_IDS: deterministic UUID strings for every path-param key
- SeedHandle: dataclass with ids/session/connection
- smoke_seed: pytest-asyncio session-scoped fixture (populated in task 2/3)
- seed_core / seed_extended: public so tests.fixtures.scenario_runner.seed
  can reuse them against the live stack (Phase 19.1).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest_asyncio
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from datetime import datetime, timezone

from app.database import Base
from app.auth.password import hash_password
from app.models.site import Site, ConnectionStatus
from app.models.site_group import SiteGroup
from app.models.user import User, UserRole
from app.models.keyword import Keyword, KeywordGroup, SearchEngine
from app.models.keyword_latest_position import KeywordLatestPosition
from app.models.gap import GapKeyword
from app.models.suggest_job import SuggestJob
from app.models.crawl import CrawlJob, CrawlJobStatus
from app.models.client_report import ClientReport
from app.models.service_credential import ServiceCredential
from app.models.audit import AuditCheckDefinition, AuditResult
from app.models.crawl import ContentType
from app.models.project import Project, ProjectStatus
from app.models.task import SeoTask, TaskType, TaskStatus, TaskPriority
from app.models.analytics import AnalysisSession, SessionStatus, ContentBrief
from app.models.cluster import KeywordCluster, ClusterIntent
from app.models.competitor import Competitor
from app.models.client import Client, ClientContact
from app.models.generated_document import GeneratedDocument
from app.models.proposal_template import ProposalTemplate, TemplateType
from app.models.commerce_check_job import CommerceCheckJob, CommerceCheckResult

# Deterministic UUID strings for URL parameter substitution.
# NOTE: "job_id" is a generic alias for suggest_job_id so routes using the
# generic name resolve to the same row.
SMOKE_IDS: dict[str, str] = {
    "site_id":        "11111111-1111-1111-1111-111111111111",
    "user_id":        "22222222-2222-2222-2222-222222222222",
    "keyword_id":     "33333333-3333-3333-3333-333333333333",
    "gap_keyword_id": "44444444-4444-4444-4444-444444444444",
    "suggest_job_id": "55555555-5555-5555-5555-555555555555",
    "crawl_job_id":   "66666666-6666-6666-6666-666666666666",
    "job_id":         "55555555-5555-5555-5555-555555555555",  # alias for suggest_job_id
    "report_id":      "77777777-7777-7777-7777-777777777777",
    "audit_id":       "88888888-8888-8888-8888-888888888888",
    "audit_check_id": "99999999-9999-9999-9999-999999999999",
    "project_id":     "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "task_id":        "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    "session_id":     "cccccccc-cccc-cccc-cccc-cccccccccccc",
    "cluster_id":     "dddddddd-dddd-dddd-dddd-dddddddddddd",
    "brief_id":       "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee",
    "competitor_id":  "ffffffff-ffff-ffff-ffff-ffffffffffff",
    "group_id":       "12121212-1212-1212-1212-121212121212",
    "client_id":      "c1c1c1c1-c1c1-c1c1-c1c1-c1c1c1c1c1c1",
    "contact_id":     "c2c2c2c2-c2c2-c2c2-c2c2-c2c2c2c2c2c2",
    "doc_id":         "d0d0d0d0-d0d0-d0d0-d0d0-d0d0d0d0d0d0",
    "template_id":    "e1e1e1e1-e1e1-e1e1-e1e1-e1e1e1e1e1e1",
    "tool_job_id":    "f1f1f1f1-f1f1-f1f1-f1f1-f1f1f1f1f1f1",
    "tool_slug":      "commercialization",
    "feature_surface_id": "a1a1a1a1-a1a1-a1a1-a1a1-a1a1a1a1a1a1",
    "surface_check_id":   "a2a2a2a2-a2a2-a2a2-a2a2-a2a2a2a2a2a2",
}


@dataclass
class SeedHandle:
    """Handle returned by the smoke_seed fixture.

    `connection` is exposed so downstream per-request sessions can bind to the
    same outer transaction via `join_transaction_mode="create_savepoint"`.
    """

    ids: dict[str, str]
    session: AsyncSession
    connection: AsyncConnection


def _u(key: str) -> UUID:
    return UUID(SMOKE_IDS[key])


_NOW = datetime.now(timezone.utc)


async def seed_core(session: AsyncSession) -> None:
    """Insert CORE entities — Wave A (Task 2)."""
    # SiteGroup first (Site FKs SET NULL to site_groups)
    session.add(
        SiteGroup(id=_u("group_id"), name="smoke-group", description="smoke test group")
    )
    await session.flush()

    # Site
    session.add(
        Site(
            id=_u("site_id"),
            name="Smoke Site",
            url="https://smoke.example.com",
            connection_status=ConnectionStatus.unknown,
            site_group_id=_u("group_id"),
            is_active=True,
        )
    )
    # Admin User
    session.add(
        User(
            id=_u("user_id"),
            username="smoke_admin",
            email="smoke@example.com",
            password_hash=hash_password("smoke-password"),
            role=UserRole.admin,
            is_active=True,
        )
    )
    await session.flush()

    # KeywordGroup
    kgroup_id = UUID("10101010-1010-1010-1010-101010101010")
    session.add(
        KeywordGroup(id=kgroup_id, site_id=_u("site_id"), name="smoke-kgroup")
    )
    await session.flush()

    # 10 Keywords: first is deterministic; mix engine yandex/google/NULL
    engines = [
        SearchEngine.yandex,
        SearchEngine.google,
        None,
        SearchEngine.yandex,
        SearchEngine.google,
        None,
        SearchEngine.yandex,
        SearchEngine.google,
        SearchEngine.yandex,
        None,
    ]
    keyword_ids: list[UUID] = []
    for i, engine in enumerate(engines):
        kid = _u("keyword_id") if i == 0 else UUID(f"3333{i:04d}-3333-3333-3333-333333333333")
        keyword_ids.append(kid)
        session.add(
            Keyword(
                id=kid,
                site_id=_u("site_id"),
                group_id=kgroup_id,
                phrase=f"smoke keyword {i}",
                frequency=100 + i,
                region="Moscow",
                engine=engine,
                target_url="https://smoke.example.com/page",
            )
        )

    # 5 KeywordLatestPosition rows
    for i in range(5):
        session.add(
            KeywordLatestPosition(
                keyword_id=keyword_ids[i],
                site_id=_u("site_id"),
                engine="yandex",
                region="Moscow",
                position=5 + i,
                previous_position=10 + i,
                delta=-5,
                url="https://smoke.example.com/page",
                checked_at=_NOW,
            )
        )

    # 2 GapKeyword
    session.add(
        GapKeyword(
            id=_u("gap_keyword_id"),
            site_id=_u("site_id"),
            competitor_domain="competitor.example",
            phrase="gap phrase 1",
            frequency=500,
            competitor_position=3,
            our_position=None,
            potential_score=87.5,
        )
    )
    session.add(
        GapKeyword(
            site_id=_u("site_id"),
            competitor_domain="competitor.example",
            phrase="gap phrase 2",
            frequency=200,
            potential_score=42.0,
        )
    )

    # SuggestJob (complete, cache_hit False)
    session.add(
        SuggestJob(
            id=_u("suggest_job_id"),
            seed="smoke seed",
            include_google=False,
            site_id=_u("site_id"),
            status="complete",
            result_count=42,
            expected_count=42,
            user_id=_u("user_id"),
        )
    )

    # CrawlJob (done)
    session.add(
        CrawlJob(
            id=_u("crawl_job_id"),
            site_id=_u("site_id"),
            status=CrawlJobStatus.done,
            pages_crawled=10,
        )
    )

    # ClientReport (ready) — blocks_config required
    session.add(
        ClientReport(
            id=_u("report_id"),
            site_id=_u("site_id"),
            blocks_config={
                "quick_wins": True,
                "audit_errors": True,
                "dead_content": True,
                "positions": True,
            },
            status="ready",
        )
    )

    # ServiceCredential rows
    for svc in ("wordstat", "gsc", "xmlproxy", "rucaptcha"):
        session.add(
            ServiceCredential(service_name=svc, credential_data="{}")
        )

    # AuditCheckDefinition
    session.add(
        AuditCheckDefinition(
            id=_u("audit_check_id"),
            code="smoke_check",
            name="Smoke Check",
            description="Smoke audit check definition",
            applies_to=ContentType.unknown,
            severity="warning",
        )
    )
    # AuditResult with explicit audit_id
    session.add(
        AuditResult(
            id=_u("audit_id"),
            site_id=_u("site_id"),
            page_url="https://smoke.example.com/page",
            check_code="smoke_check",
            status="warning",
            details="smoke audit result",
        )
    )
    await session.flush()


async def seed_extended(session: AsyncSession) -> None:
    """Insert EXTENDED entities — Wave B (Task 3).

    Substitutions from plan (documented for Plan 02 SMOKE_SKIP awareness):
    - `Task` model is `SeoTask` (app/models/task.py); seeded as SeoTask row
    - `AnalyticsSession` model is `AnalysisSession` (app/models/analytics.py)
    - `Brief` model is `ContentBrief` (app/models/analytics.py)
    - `KeywordCluster` FK is `site_id` (not project_id per plan)
    """
    # Project
    session.add(
        Project(
            id=_u("project_id"),
            site_id=_u("site_id"),
            name="smoke-project",
            status=ProjectStatus.active,
        )
    )
    # SeoTask (ORM Task row)
    session.add(
        SeoTask(
            id=_u("task_id"),
            site_id=_u("site_id"),
            task_type=TaskType.manual,
            status=TaskStatus.open,
            url="https://smoke.example.com/page",
            title="smoke task",
            priority=TaskPriority.p3,
        )
    )
    # AnalysisSession (session_id)
    session.add(
        AnalysisSession(
            id=_u("session_id"),
            site_id=_u("site_id"),
            name="smoke-session",
            status=SessionStatus.draft,
            keyword_ids=[],
            keyword_count=0,
        )
    )
    # KeywordCluster
    session.add(
        KeywordCluster(
            id=_u("cluster_id"),
            site_id=_u("site_id"),
            name="smoke-cluster",
            intent=ClusterIntent.unknown,
        )
    )
    await session.flush()

    # ContentBrief — requires session_id (just created)
    session.add(
        ContentBrief(
            id=_u("brief_id"),
            session_id=_u("session_id"),
            site_id=_u("site_id"),
            title="smoke brief",
            keywords_json=[],
        )
    )
    # Competitor
    session.add(
        Competitor(
            id=_u("competitor_id"),
            site_id=_u("site_id"),
            domain="competitor.example",
            name="Smoke Competitor",
        )
    )

    # Client (CRM)
    session.add(
        Client(
            id=_u("client_id"),
            company_name="Smoke Client LLC",
            manager_id=_u("user_id"),
        )
    )
    await session.flush()

    # ClientContact
    session.add(
        ClientContact(
            id=_u("contact_id"),
            client_id=_u("client_id"),
            name="Smoke Contact",
            email="contact@smoke.example.com",
        )
    )

    # ProposalTemplate (needed for GeneratedDocument FK)
    session.add(
        ProposalTemplate(
            id=_u("template_id"),
            name="Smoke Template",
            template_type=TemplateType.proposal,
            body="<h1>Smoke</h1>",
            created_by_id=_u("user_id"),
        )
    )
    await session.flush()

    # GeneratedDocument (doc_id)
    session.add(
        GeneratedDocument(
            id=_u("doc_id"),
            client_id=_u("client_id"),
            site_id=_u("site_id"),
            template_id=_u("template_id"),
            document_type=TemplateType.proposal,
            status="ready",
            file_name="smoke-doc.pdf",
        )
    )
    await session.flush()

    # CommerceCheckJob (tool_job_id) — Phase 24 tools smoke seed
    session.add(
        CommerceCheckJob(
            id=_u("tool_job_id"),
            status="complete",
            input_phrases=["test phrase"],
            phrase_count=1,
            result_count=1,
            user_id=_u("user_id"),
            created_at=_NOW,
            completed_at=_NOW,
        )
    )
    await session.flush()

    # CommerceCheckResult linked to tool_job_id
    session.add(
        CommerceCheckResult(
            job_id=_u("tool_job_id"),
            phrase="test phrase",
            commercialization=50,
            intent="mixed",
            geo_dependent=False,
            localized=False,
        )
    )
    await session.flush()

    # QA Surface Tracker seed (Phase 999.10)
    from app.models.qa_surface import FeatureSurface, SurfaceCheck, Surface, CheckStatus

    feature_surface = FeatureSurface(
        id=_u("feature_surface_id"),
        slug="smoke-test-flow",
        name="Smoke Test Flow",
        description="Seeded for smoke testing",
        retest_days=30,
        is_active=True,
    )
    session.add(feature_surface)
    await session.flush()

    # Create one SurfaceCheck for the smoke ID (desktop), plus the other two surfaces
    for surface in Surface:
        check_id = _u("surface_check_id") if surface == Surface.desktop else uuid4()
        session.add(
            SurfaceCheck(
                id=check_id,
                feature_id=_u("feature_surface_id"),
                surface=surface,
                status=CheckStatus.not_tested,
            )
        )
    await session.flush()


try:
    from app.config import settings
    TEST_DATABASE_URL = settings.DATABASE_URL.replace(
        f"/{settings.DATABASE_URL.split('/')[-1]}",
        "/seo_platform_test",
    )
except Exception:
    TEST_DATABASE_URL = (
        "postgresql+asyncpg://seo_user:changeme@postgres:5432/seo_platform_test"
    )


@pytest_asyncio.fixture(scope="session")
async def smoke_seed() -> Any:
    """Session-scoped smoke seed. Populated in tasks 2/3."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, checkfirst=True)

    conn = await engine.connect()
    outer_trans = await conn.begin()

    Session = async_sessionmaker(
        bind=conn,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    session = Session()
    try:
        await seed_core(session)
        await seed_extended(session)
        await session.flush()
        yield SeedHandle(ids=SMOKE_IDS, session=session, connection=conn)
    finally:
        await session.close()
        await outer_trans.rollback()
        await conn.close()
        await engine.dispose()
