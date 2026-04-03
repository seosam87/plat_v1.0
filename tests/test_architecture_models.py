import uuid

from app.models.architecture import PageLink, SitemapEntry
from app.models.crawl import ArchitectureRole, Page


def test_architecture_role_enum():
    assert len(ArchitectureRole) == 8
    assert ArchitectureRole.pillar.value == "pillar"
    assert ArchitectureRole.link_accelerator.value == "link_accelerator"


def test_page_has_source_and_role():
    assert hasattr(Page, "source")
    assert hasattr(Page, "architecture_role")


def test_sitemap_entry_fields():
    e = SitemapEntry(
        site_id=uuid.uuid4(),
        url="https://e.com/page/",
        in_sitemap=True,
        in_crawl=False,
        status="missing",
    )
    assert e.status == "missing"


def test_page_link_fields():
    pl = PageLink(
        site_id=uuid.uuid4(),
        crawl_job_id=uuid.uuid4(),
        source_url="https://e.com/a/",
        target_url="https://e.com/b/",
        anchor_text="link text",
    )
    assert pl.anchor_text == "link text"


def test_architecture_role_all_values():
    expected = {"pillar", "service", "subservice", "article", "trigger", "authority", "link_accelerator", "unknown"}
    actual = {r.value for r in ArchitectureRole}
    assert actual == expected
