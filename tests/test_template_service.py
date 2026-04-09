"""Tests for template service layer: template_service.py + template_variable_resolver.py.

Uses real DB session from conftest.py (SAVEPOINT-isolated) for service tests.
Render tests call render_template_preview directly (no DB needed).
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.proposal_template import ProposalTemplate, TemplateType
from app.models.site import ConnectionStatus, Site
from app.models.client import Client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def template(db_session: AsyncSession) -> ProposalTemplate:
    """A basic proposal template."""
    t = ProposalTemplate(
        name="Test Proposal",
        template_type=TemplateType.proposal,
        description="A test proposal template",
        body="Hello {{ client.name }}",
    )
    db_session.add(t)
    await db_session.flush()
    return t


@pytest_asyncio.fixture
async def client_row(db_session: AsyncSession) -> Client:
    """A basic client."""
    c = Client(
        company_name="Acme Corp",
        legal_name="Acme Corporation LLC",
        inn="1234567890",
        email="info@acme.com",
        phone="+7-999-000-0000",
    )
    db_session.add(c)
    await db_session.flush()
    return c


@pytest_asyncio.fixture
async def site_row(db_session: AsyncSession, client_row: Client) -> Site:
    """A basic site linked to a client."""
    s = Site(
        name="Acme Website",
        url="https://acme.com",
        connection_status=ConnectionStatus.connected,
        client_id=client_row.id,
        metrika_counter_id="98765432",
    )
    db_session.add(s)
    await db_session.flush()
    return s


# ---------------------------------------------------------------------------
# template_service: list_templates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_templates_empty(db_session: AsyncSession):
    """Returns empty list when no templates exist."""
    from app.services.template_service import list_templates

    result = await list_templates(db_session)
    assert result == []


@pytest.mark.asyncio
async def test_list_templates_returns_list(
    db_session: AsyncSession, template: ProposalTemplate
):
    """Returns list of ProposalTemplate objects when templates exist."""
    from app.services.template_service import list_templates

    result = await list_templates(db_session)
    assert len(result) >= 1
    assert any(t.id == template.id for t in result)


@pytest.mark.asyncio
async def test_list_templates_filter_by_type(
    db_session: AsyncSession, template: ProposalTemplate
):
    """Filters by template_type when provided."""
    from app.services.template_service import list_templates

    proposals = await list_templates(db_session, template_type=TemplateType.proposal)
    assert any(t.id == template.id for t in proposals)

    briefs = await list_templates(db_session, template_type=TemplateType.brief)
    assert not any(t.id == template.id for t in briefs)


# ---------------------------------------------------------------------------
# template_service: get_template
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_template(db_session: AsyncSession, template: ProposalTemplate):
    """Returns template by UUID."""
    from app.services.template_service import get_template

    result = await get_template(db_session, template.id)
    assert result is not None
    assert result.id == template.id
    assert result.name == "Test Proposal"


@pytest.mark.asyncio
async def test_get_template_missing(db_session: AsyncSession):
    """Returns None for missing UUID."""
    from app.services.template_service import get_template

    result = await get_template(db_session, uuid.uuid4())
    assert result is None


# ---------------------------------------------------------------------------
# template_service: create_template
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_template(db_session: AsyncSession):
    """Creates template with name, type, description, body; returns ProposalTemplate with UUID."""
    from app.services.template_service import create_template

    creator_id = uuid.uuid4()
    result = await create_template(
        db_session,
        name="New Template",
        template_type=TemplateType.audit_report,
        description="An audit report template",
        body="## Site Audit for {{ site.domain }}",
        created_by_id=creator_id,
    )
    assert result is not None
    assert isinstance(result.id, uuid.UUID)
    assert result.name == "New Template"
    assert result.template_type == TemplateType.audit_report
    assert result.description == "An audit report template"
    assert result.body == "## Site Audit for {{ site.domain }}"


# ---------------------------------------------------------------------------
# template_service: update_template
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_template(db_session: AsyncSession, template: ProposalTemplate):
    """Updates name/body/description; returns updated template."""
    from app.services.template_service import update_template

    result = await update_template(
        db_session,
        template.id,
        name="Updated Name",
        template_type=TemplateType.brief,
        description="Updated description",
        body="Updated body {{ client.name }}",
    )
    assert result is not None
    assert result.name == "Updated Name"
    assert result.template_type == TemplateType.brief
    assert result.body == "Updated body {{ client.name }}"


@pytest.mark.asyncio
async def test_update_template_missing(db_session: AsyncSession):
    """Returns None when template not found."""
    from app.services.template_service import update_template

    result = await update_template(
        db_session,
        uuid.uuid4(),
        name="X",
        template_type=TemplateType.proposal,
        description=None,
        body="X",
    )
    assert result is None


# ---------------------------------------------------------------------------
# template_service: delete_template
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_template(db_session: AsyncSession, template: ProposalTemplate):
    """Hard deletes template; subsequent get returns None."""
    from app.services.template_service import delete_template, get_template

    deleted = await delete_template(db_session, template.id)
    assert deleted is True

    result = await get_template(db_session, template.id)
    assert result is None


@pytest.mark.asyncio
async def test_delete_template_missing(db_session: AsyncSession):
    """Returns False when template not found."""
    from app.services.template_service import delete_template

    result = await delete_template(db_session, uuid.uuid4())
    assert result is False


# ---------------------------------------------------------------------------
# template_service: clone_template
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_clone_template(db_session: AsyncSession, template: ProposalTemplate):
    """Creates copy with name '{original} (копия)'; new UUID; same body/type/description."""
    from app.services.template_service import clone_template

    creator_id = uuid.uuid4()
    clone = await clone_template(db_session, template.id, created_by_id=creator_id)

    assert clone is not None
    assert clone.id != template.id
    assert clone.name == f"{template.name} (копия)"
    assert clone.template_type == template.template_type
    assert clone.body == template.body
    assert clone.description == template.description


@pytest.mark.asyncio
async def test_clone_template_missing(db_session: AsyncSession):
    """Returns None when original template not found."""
    from app.services.template_service import clone_template

    result = await clone_template(db_session, uuid.uuid4(), created_by_id=uuid.uuid4())
    assert result is None


# ---------------------------------------------------------------------------
# template_variable_resolver: resolve_template_variables
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_variables(
    db_session: AsyncSession, client_row: Client, site_row: Site
):
    """Returns dict with keys 'client' and 'site'; plain scalar values only."""
    from app.services.template_variable_resolver import resolve_template_variables

    result = await resolve_template_variables(db_session, client_row.id, site_row.id)

    assert "client" in result
    assert "site" in result

    client_data = result["client"]
    assert client_data["name"] == "Acme Corp"
    assert client_data["legal_name"] == "Acme Corporation LLC"
    assert client_data["inn"] == "1234567890"
    assert client_data["email"] == "info@acme.com"
    assert client_data["phone"] == "+7-999-000-0000"
    assert "manager" in client_data

    site_data = result["site"]
    assert site_data["url"] == "https://acme.com"
    assert "domain" in site_data
    assert "top_positions_count" in site_data
    assert "audit_errors_count" in site_data
    assert "last_crawl_date" in site_data
    assert "gsc_connected" in site_data
    assert "metrika_id" in site_data

    # CRITICAL: no ORM objects — only plain Python types
    for key, val in client_data.items():
        assert not hasattr(val, "_sa_instance_state"), f"client.{key} is an ORM object"
    for key, val in site_data.items():
        assert not hasattr(val, "_sa_instance_state"), f"site.{key} is an ORM object"


# ---------------------------------------------------------------------------
# template_variable_resolver: render_template_preview
# ---------------------------------------------------------------------------


def test_render_template_preview():
    """Renders 'Hello {{ client.name }}' with context producing 'Hello Acme'."""
    from app.services.template_variable_resolver import render_template_preview

    result = render_template_preview(
        "Hello {{ client.name }}", {"client": {"name": "Acme"}}
    )
    assert result == "Hello Acme"


def test_render_unresolved_variable():
    """Renders '{{ unknown_var }}' producing HTML span with class 'unresolved-var'."""
    from app.services.template_variable_resolver import render_template_preview

    result = render_template_preview("{{ unknown_var }}", {})
    assert "unresolved-var" in result
    assert "unknown_var" in result


def test_render_syntax_error():
    """Renders '{% if %}' producing error message HTML (not a crash)."""
    from app.services.template_variable_resolver import render_template_preview

    result = render_template_preview("{% if %}", {})
    # Should return an error message string, not raise
    assert isinstance(result, str)
    assert len(result) > 0
    # Should indicate an error, not render valid content
    assert "error" in result.lower() or "Error" in result or "шаблон" in result.lower()
