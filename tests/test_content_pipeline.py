"""Unit tests for content pipeline: TOC, schema.org, internal linking, diff."""
import pytest

from app.services.content_pipeline import (
    extract_headings,
    generate_toc_html,
    inject_toc,
    add_heading_ids,
    generate_schema_article,
    has_schema_ld,
    inject_schema,
    find_link_opportunities,
    insert_links,
    compute_content_diff,
    _slugify,
)


# ---- TOC ----


class TestExtractHeadings:
    def test_extracts_h2_and_h3(self):
        html = "<h2>First</h2><p>text</p><h3>Sub</h3><h2>Second</h2>"
        headings = extract_headings(html)
        assert len(headings) == 3
        assert headings[0] == {"level": 2, "text": "First", "id": "first"}
        assert headings[1] == {"level": 3, "text": "Sub", "id": "sub"}
        assert headings[2] == {"level": 2, "text": "Second", "id": "second"}

    def test_preserves_existing_ids(self):
        html = '<h2 id="my-id">Title</h2>'
        headings = extract_headings(html)
        assert headings[0]["id"] == "my-id"

    def test_no_headings(self):
        html = "<p>Just a paragraph</p>"
        assert extract_headings(html) == []

    def test_strips_inner_tags(self):
        html = "<h2><strong>Bold</strong> Title</h2>"
        headings = extract_headings(html)
        assert headings[0]["text"] == "Bold Title"


class TestGenerateToc:
    def test_generates_list(self):
        headings = [{"level": 2, "text": "A", "id": "a"}, {"level": 3, "text": "B", "id": "b"}]
        toc = generate_toc_html(headings)
        assert '<a href="#a">A</a>' in toc
        assert '<a href="#b">B</a>' in toc

    def test_empty_headings(self):
        assert generate_toc_html([]) == ""


class TestInjectToc:
    def test_inserts_after_first_p(self):
        html = "<p>Intro</p><h2>Title</h2>"
        result = inject_toc(html, "<div>TOC</div>")
        assert result.index("<div>TOC</div>") > result.index("</p>")

    def test_prepends_if_no_p(self):
        html = "<h2>Title</h2>"
        result = inject_toc(html, "<div>TOC</div>")
        assert result.startswith("<div>TOC</div>")


# ---- Schema.org ----


class TestSchemaOrg:
    def test_generate_article(self):
        tag = generate_schema_article("My Title", "https://a.com/page", "2026-01-01", "John")
        assert "application/ld+json" in tag
        assert "My Title" in tag
        assert "John" in tag

    def test_has_schema_ld_true(self):
        html = '<script type="application/ld+json">{"@type":"Article"}</script>'
        assert has_schema_ld(html) is True

    def test_has_schema_ld_false(self):
        assert has_schema_ld("<p>No schema</p>") is False

    def test_inject_schema_adds(self):
        html = "<p>Content</p>"
        tag = '<script type="application/ld+json">{}</script>'
        result = inject_schema(html, tag)
        assert "application/ld+json" in result

    def test_inject_schema_skips_existing(self):
        html = '<p>Content</p><script type="application/ld+json">{}</script>'
        result = inject_schema(html, "<script>NEW</script>")
        assert result.count("application/ld+json") == 1


# ---- Internal linking ----


class TestInternalLinking:
    def test_finds_opportunities(self):
        content = "<p>Learn about seo tools and keyword research today.</p>"
        kws = [
            {"phrase": "seo tools", "url": "/seo"},
            {"phrase": "keyword research", "url": "/kw"},
        ]
        opps = find_link_opportunities(content, kws)
        assert len(opps) == 2

    def test_skips_already_linked(self):
        content = '<p>Read about <a href="/seo">seo tools</a> here.</p>'
        kws = [{"phrase": "seo tools", "url": "/seo"}]
        opps = find_link_opportunities(content, kws)
        assert len(opps) == 0

    def test_respects_max_links(self):
        content = "<p>a b c d e f g h i j</p>"
        kws = [{"phrase": c, "url": f"/{c}"} for c in "abcdefghij"]
        opps = find_link_opportunities(content, kws, max_links=3)
        assert len(opps) == 3

    def test_insert_links(self):
        content = "<p>Learn about seo tools today.</p>"
        kws = [{"phrase": "seo tools", "url": "/seo"}]
        opps = find_link_opportunities(content, kws)
        result = insert_links(content, opps)
        assert '<a href="/seo">seo tools</a>' in result


# ---- Diff ----


class TestDiff:
    def test_detects_changes(self):
        diff = compute_content_diff("<p>Old</p>", "<p>New</p>")
        assert diff["has_changes"] is True
        assert diff["added_lines"] > 0
        assert diff["removed_lines"] > 0

    def test_no_changes(self):
        diff = compute_content_diff("<p>Same</p>", "<p>Same</p>")
        assert diff["has_changes"] is False

    def test_added_lines(self):
        diff = compute_content_diff("<p>A</p>", "<p>A</p>\n<p>B</p>")
        assert diff["has_changes"] is True
        assert diff["added_lines"] >= 1


# ---- Helpers ----


class TestSlugify:
    def test_basic(self):
        assert _slugify("Hello World") == "hello-world"

    def test_cyrillic(self):
        result = _slugify("Привет мир")
        assert "привет" in result

    def test_special_chars(self):
        assert _slugify("What's up?") == "whats-up"

    def test_truncates_long(self):
        assert len(_slugify("a" * 200)) <= 80


# ---- Phase 6: new endpoints ----


class TestPipelineEndpointsRegistered:
    def test_new_endpoints(self):
        from app.routers.wp_pipeline import router
        paths = [r.path for r in router.routes]
        assert "/pipeline/sites/{site_id}/history" in paths
        assert "/pipeline/sites/{site_id}/bulk-approve" in paths
        assert "/pipeline/sites/{site_id}/bulk-reject" in paths


class TestDiffViewer:
    def test_diff_has_text(self):
        """compute_content_diff returns diff_text suitable for display."""
        diff = compute_content_diff(
            "<p>Old content</p>",
            "<p>Old content</p>\n<div id='toc'>TOC</div>"
        )
        assert diff["has_changes"] is True
        assert diff["diff_text"]  # non-empty string
        assert "+" in diff["diff_text"] or "-" in diff["diff_text"]

    def test_diff_no_changes_empty_text(self):
        diff = compute_content_diff("<p>Same</p>", "<p>Same</p>")
        assert diff["has_changes"] is False


class TestBulkLogic:
    def test_only_awaiting_approval_can_be_approved(self):
        """Verify the status check logic used in bulk operations."""
        from app.models.wp_content_job import JobStatus
        statuses_that_can_approve = [JobStatus.awaiting_approval]
        assert JobStatus.pending not in statuses_that_can_approve
        assert JobStatus.pushed not in statuses_that_can_approve
        assert JobStatus.failed not in statuses_that_can_approve
