"""Integration tests for the session-scoped smoke_seed fixture (Phase 15.1)."""
from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import select, func

from tests.fixtures.smoke_seed import SMOKE_IDS, smoke_seed  # noqa: F401
from app.models.site import Site
from app.models.user import User
from app.models.keyword import Keyword
from app.models.gap import GapKeyword
from app.models.suggest_job import SuggestJob
from app.models.crawl import CrawlJob
from app.models.client_report import ClientReport
from app.models.audit import AuditCheckDefinition, AuditResult
from app.models.project import Project
from app.models.task import SeoTask
from app.models.analytics import AnalysisSession, ContentBrief
from app.models.cluster import KeywordCluster
from app.models.competitor import Competitor
from app.models.site_group import SiteGroup


pytestmark = pytest.mark.asyncio(scope="session")


async def test_site_seeded(smoke_seed):
    res = await smoke_seed.session.execute(
        select(Site).where(Site.id == UUID(SMOKE_IDS["site_id"]))
    )
    assert res.scalar_one().url == "https://smoke.example.com"


async def test_user_seeded(smoke_seed):
    res = await smoke_seed.session.execute(
        select(User).where(User.id == UUID(SMOKE_IDS["user_id"]))
    )
    assert res.scalar_one().username == "smoke_admin"


async def test_keyword_count(smoke_seed):
    res = await smoke_seed.session.execute(
        select(func.count(Keyword.id)).where(Keyword.site_id == UUID(SMOKE_IDS["site_id"]))
    )
    assert res.scalar_one() == 10


async def test_gap_keyword_count(smoke_seed):
    res = await smoke_seed.session.execute(
        select(func.count(GapKeyword.id)).where(GapKeyword.site_id == UUID(SMOKE_IDS["site_id"]))
    )
    assert res.scalar_one() == 2


async def test_suggest_job_seeded(smoke_seed):
    res = await smoke_seed.session.execute(
        select(SuggestJob).where(SuggestJob.id == UUID(SMOKE_IDS["suggest_job_id"]))
    )
    assert res.scalar_one().status == "complete"


async def test_crawl_job_seeded(smoke_seed):
    res = await smoke_seed.session.execute(
        select(CrawlJob).where(CrawlJob.id == UUID(SMOKE_IDS["crawl_job_id"]))
    )
    assert res.scalar_one() is not None


async def test_client_report_seeded(smoke_seed):
    res = await smoke_seed.session.execute(
        select(ClientReport).where(ClientReport.id == UUID(SMOKE_IDS["report_id"]))
    )
    assert res.scalar_one().status == "ready"


async def test_audit_check_definition_explicit_id(smoke_seed):
    res = await smoke_seed.session.execute(
        select(AuditCheckDefinition).where(
            AuditCheckDefinition.id == UUID(SMOKE_IDS["audit_check_id"])
        )
    )
    assert res.scalar_one().code == "smoke_check"


async def test_audit_result_explicit_id(smoke_seed):
    res = await smoke_seed.session.execute(
        select(AuditResult).where(AuditResult.id == UUID(SMOKE_IDS["audit_id"]))
    )
    assert res.scalar_one().check_code == "smoke_check"


# ---- Extended entities (Task 3) ----

async def test_site_group_seeded(smoke_seed):
    res = await smoke_seed.session.execute(
        select(SiteGroup).where(SiteGroup.id == UUID(SMOKE_IDS["group_id"]))
    )
    assert res.scalar_one().name == "smoke-group"


async def test_project_seeded(smoke_seed):
    res = await smoke_seed.session.execute(
        select(Project).where(Project.id == UUID(SMOKE_IDS["project_id"]))
    )
    assert res.scalar_one().name == "smoke-project"


async def test_task_seeded(smoke_seed):
    res = await smoke_seed.session.execute(
        select(SeoTask).where(SeoTask.id == UUID(SMOKE_IDS["task_id"]))
    )
    assert res.scalar_one().title == "smoke task"


async def test_analysis_session_seeded(smoke_seed):
    res = await smoke_seed.session.execute(
        select(AnalysisSession).where(AnalysisSession.id == UUID(SMOKE_IDS["session_id"]))
    )
    assert res.scalar_one().name == "smoke-session"


async def test_keyword_cluster_seeded(smoke_seed):
    res = await smoke_seed.session.execute(
        select(KeywordCluster).where(KeywordCluster.id == UUID(SMOKE_IDS["cluster_id"]))
    )
    assert res.scalar_one().name == "smoke-cluster"


async def test_brief_seeded(smoke_seed):
    res = await smoke_seed.session.execute(
        select(ContentBrief).where(ContentBrief.id == UUID(SMOKE_IDS["brief_id"]))
    )
    assert res.scalar_one().title == "smoke brief"


async def test_competitor_seeded(smoke_seed):
    res = await smoke_seed.session.execute(
        select(Competitor).where(Competitor.id == UUID(SMOKE_IDS["competitor_id"]))
    )
    assert res.scalar_one().domain == "competitor.example"
