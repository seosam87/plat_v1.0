import uuid

from app.models.analytics import (
    AnalysisSession,
    CompetitorPageData,
    ContentBrief,
    SessionSerpResult,
    SessionStatus,
)


def test_session_status_enum():
    assert SessionStatus.draft.value == "draft"
    assert SessionStatus.brief_created.value == "brief_created"
    assert len(SessionStatus) == 7


def test_analysis_session_fields():
    s = AnalysisSession(
        site_id=uuid.uuid4(),
        name="Test session",
        keyword_ids=[str(uuid.uuid4())],
        keyword_count=1,
    )
    assert s.name == "Test session"
    assert s.keyword_count == 1


def test_session_serp_result_fields():
    r = SessionSerpResult(
        session_id=uuid.uuid4(),
        keyword_id=uuid.uuid4(),
        keyword_phrase="seo продвижение",
        results_json=[{"position": 1, "url": "https://e.com/", "domain": "e.com", "title": "Title"}],
    )
    assert r.keyword_phrase == "seo продвижение"
    assert len(r.results_json) == 1


def test_competitor_page_data_fields():
    c = CompetitorPageData(
        session_id=uuid.uuid4(),
        url="https://competitor.com/page/",
        domain="competitor.com",
        title="Competitor Title",
        crawl_mode="light",
    )
    assert c.crawl_mode == "light"
    assert c.domain == "competitor.com"


def test_content_brief_fields():
    b = ContentBrief(
        session_id=uuid.uuid4(),
        site_id=uuid.uuid4(),
        title="ТЗ: SEO продвижение",
        keywords_json=[{"phrase": "seo", "frequency": 1000}],
    )
    assert b.title == "ТЗ: SEO продвижение"
    assert len(b.keywords_json) == 1
