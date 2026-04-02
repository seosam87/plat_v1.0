"""Tests for schema template engine: rendering, type selection, page data."""
import json

from app.services.schema_service import (
    generate_schema_tag,
    get_page_data_for_schema,
    render_schema_template,
    select_schema_type_for_page,
)


# ---- Render tests ----


def test_render_template_basic():
    tpl = '{"@type":"Article","headline":"{{title}}","url":"{{url}}"}'
    result = render_schema_template(tpl, {"title": "Test Page", "url": "https://e.com/"})
    parsed = json.loads(result)
    assert parsed["headline"] == "Test Page"
    assert parsed["url"] == "https://e.com/"


def test_render_template_missing_placeholder():
    tpl = '{"@type":"Article","headline":"{{title}}","author":"{{author}}"}'
    result = render_schema_template(tpl, {"title": "Page"})
    parsed = json.loads(result)
    assert parsed["headline"] == "Page"
    assert parsed["author"] == ""


def test_render_template_valid_json():
    tpl = '{"@context":"https://schema.org","@type":"Service","name":"{{title}}"}'
    result = render_schema_template(tpl, {"title": "SEO Audit"})
    parsed = json.loads(result)
    assert parsed["@context"] == "https://schema.org"
    assert parsed["name"] == "SEO Audit"


def test_render_template_cyrillic():
    tpl = '{"@type":"Article","headline":"{{title}}"}'
    result = render_schema_template(tpl, {"title": "Продвижение сайтов"})
    parsed = json.loads(result)
    assert parsed["headline"] == "Продвижение сайтов"


def test_generate_schema_tag():
    rendered = '{"@type":"Article"}'
    tag = generate_schema_tag(rendered)
    assert tag == '<script type="application/ld+json">{"@type":"Article"}</script>'


# ---- Selection tests ----


def test_select_article_for_informational():
    assert select_schema_type_for_page("informational", "article") == "Article"


def test_select_product_for_commercial_product():
    assert select_schema_type_for_page("commercial", "product") == "Product"


def test_select_service_for_commercial_landing():
    assert select_schema_type_for_page("commercial", "landing") == "Service"


def test_select_localbusiness_for_commercial_category():
    assert select_schema_type_for_page("commercial", "category") == "LocalBusiness"


def test_select_default_article():
    assert select_schema_type_for_page("unknown", "unknown") == "Article"


# ---- Page data tests ----


def test_get_page_data_for_schema():
    data = get_page_data_for_schema(
        title="Test", url="https://e.com/", description="Desc",
        site_name="MySite", author="John", date_published="2026-01-01",
    )
    assert data["title"] == "Test"
    assert data["url"] == "https://e.com/"
    assert data["site_name"] == "MySite"


def test_get_page_data_defaults():
    data = get_page_data_for_schema(title="T", url="https://e.com/")
    assert data["description"] == ""
    assert data["author"] == "Author"
    assert data["date_published"] == ""
