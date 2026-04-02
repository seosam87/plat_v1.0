import uuid

from app.models.audit import AuditCheckDefinition, AuditResult, SchemaTemplate
from app.models.crawl import ContentType, Page
from app.models.site import Site


def test_content_type_enum():
    assert ContentType.informational.value == "informational"
    assert ContentType.commercial.value == "commercial"
    assert ContentType.unknown.value == "unknown"


def test_page_has_content_type():
    assert hasattr(Page, "content_type")


def test_site_has_cta_template():
    assert hasattr(Site, "cta_template_html")


def test_audit_check_definition_fields():
    check = AuditCheckDefinition(
        code="toc_present",
        name="Наличие TOC",
        severity="warning",
        auto_fixable=True,
        fix_action="inject_toc",
    )
    assert check.code == "toc_present"
    assert check.auto_fixable is True
    assert check.fix_action == "inject_toc"


def test_audit_result_fields():
    result = AuditResult(
        site_id=uuid.uuid4(),
        page_url="https://example.com/page/",
        check_code="toc_present",
        status="fail",
    )
    assert result.status == "fail"
    assert result.check_code == "toc_present"


def test_schema_template_fields():
    tpl = SchemaTemplate(
        schema_type="Article",
        name="Default Article",
        template_json='{"@context":"https://schema.org","@type":"Article"}',
        is_default=True,
    )
    assert tpl.schema_type == "Article"
    assert tpl.is_default is True
