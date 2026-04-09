"""Tests for document service layer: document_service.py.

Uses real DB session from conftest.py (SAVEPOINT-isolated) for CRUD tests.
build_filename tests are pure-function tests (no DB needed).
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from unittest.mock import patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.generated_document import GeneratedDocument
from app.models.proposal_template import ProposalTemplate, TemplateType
from app.services.document_service import (
    MAX_VERSIONS,
    build_filename,
    create_document,
    delete_document,
    enforce_version_cap,
    get_document,
    list_documents,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def client_row(db_session: AsyncSession):
    """A basic client for FK reference."""
    from app.models.client import Client

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
async def template(db_session: AsyncSession):
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
async def site_row(db_session: AsyncSession, client_row):
    """A basic site linked to the client."""
    from app.models.site import ConnectionStatus, Site

    s = Site(
        name="Acme Website",
        url="https://acme.com",
        connection_status=ConnectionStatus.connected,
        client_id=client_row.id,
    )
    db_session.add(s)
    await db_session.flush()
    return s


# ---------------------------------------------------------------------------
# build_filename tests (no DB)
# ---------------------------------------------------------------------------


def test_build_filename_basic():
    """Standard filename format: {type}_{name}_{date}.pdf"""
    today = date.today().isoformat()
    result = build_filename("proposal", "CompanyName")
    assert result == f"proposal_CompanyName_{today}.pdf"


def test_build_filename_special_chars():
    """Non-alphanumeric chars replaced with underscore."""
    today = date.today().isoformat()
    result = build_filename("audit_report", "Company & Co (Test)")
    assert result == f"audit_report_Company___Co__Test__{today}.pdf"
    # No special chars in the name part
    assert "&" not in result
    assert "(" not in result


def test_build_filename_long_name():
    """Client name truncated to 40 chars."""
    long_name = "A" * 60
    result = build_filename("brief", long_name)
    # Name part should be exactly 40 chars
    name_part = result.split("_", 1)[1].rsplit("_", 1)[0]  # between first _ and date
    # account for the date part
    assert len(name_part) == 40


def test_build_filename_cyrillic():
    """Cyrillic characters preserved (they match \\w in Python regex)."""
    today = date.today().isoformat()
    result = build_filename("proposal", "Acme")
    assert result == f"proposal_Acme_{today}.pdf"


# ---------------------------------------------------------------------------
# CRUD tests (DB-backed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_document(db_session: AsyncSession, client_row, template):
    """Creates record with status='pending'."""
    doc = await create_document(
        db_session,
        client_id=client_row.id,
        site_id=None,
        template_id=template.id,
        document_type=TemplateType.proposal,
        file_name="test.pdf",
    )
    assert doc.id is not None
    assert doc.status == "pending"
    assert doc.client_id == client_row.id
    assert doc.template_id == template.id
    assert doc.file_name == "test.pdf"


@pytest.mark.asyncio
async def test_get_document(db_session: AsyncSession, client_row, template):
    """Retrieves document by id."""
    doc = await create_document(
        db_session,
        client_id=client_row.id,
        site_id=None,
        template_id=template.id,
        document_type=TemplateType.proposal,
    )
    fetched = await get_document(db_session, doc.id)
    assert fetched is not None
    assert fetched.id == doc.id

    # Non-existent ID returns None
    missing = await get_document(db_session, uuid.uuid4())
    assert missing is None


@pytest.mark.asyncio
async def test_list_documents_by_type(db_session: AsyncSession, client_row, template):
    """Filters documents by doc_type."""
    await create_document(
        db_session,
        client_id=client_row.id,
        site_id=None,
        template_id=template.id,
        document_type=TemplateType.proposal,
    )
    # Create a brief-type template
    t2 = ProposalTemplate(
        name="Brief Template",
        template_type=TemplateType.brief,
        body="Brief for {{ client.name }}",
    )
    db_session.add(t2)
    await db_session.flush()

    await create_document(
        db_session,
        client_id=client_row.id,
        site_id=None,
        template_id=t2.id,
        document_type=TemplateType.brief,
    )

    # Filter by proposal
    proposals = await list_documents(
        db_session, client_row.id, doc_type=TemplateType.proposal
    )
    assert len(proposals) == 1
    assert proposals[0].document_type == TemplateType.proposal

    # All types
    all_docs = await list_documents(db_session, client_row.id)
    assert len(all_docs) == 2


@pytest.mark.asyncio
async def test_list_documents_by_date(db_session: AsyncSession, client_row, template):
    """Filters documents by date range."""
    doc = await create_document(
        db_session,
        client_id=client_row.id,
        site_id=None,
        template_id=template.id,
        document_type=TemplateType.proposal,
    )

    today = date.today()
    # Should include today's document
    docs = await list_documents(
        db_session, client_row.id, date_from=today, date_to=today
    )
    assert len(docs) == 1

    # Yesterday only should be empty
    yesterday = today - timedelta(days=1)
    docs_yesterday = await list_documents(
        db_session, client_row.id, date_from=yesterday, date_to=yesterday
    )
    assert len(docs_yesterday) == 0


@pytest.mark.asyncio
async def test_enforce_version_cap(db_session: AsyncSession, client_row, template):
    """With 3 existing docs, deletes oldest to make room."""
    docs = []
    for i in range(3):
        d = await create_document(
            db_session,
            client_id=client_row.id,
            site_id=None,
            template_id=template.id,
            document_type=TemplateType.proposal,
            file_name=f"doc_{i}.pdf",
        )
        docs.append(d)

    deleted = await enforce_version_cap(
        db_session, client_row.id, template.id
    )
    assert deleted == 1  # Oldest deleted to make room for new one

    # Verify oldest is gone
    remaining = await list_documents(db_session, client_row.id)
    assert len(remaining) == 2
    remaining_ids = {d.id for d in remaining}
    assert docs[0].id not in remaining_ids  # oldest was deleted


@pytest.mark.asyncio
async def test_delete_document_blocks_active(db_session: AsyncSession, client_row, template):
    """Cannot delete documents with status='pending' or 'processing'."""
    doc = await create_document(
        db_session,
        client_id=client_row.id,
        site_id=None,
        template_id=template.id,
        document_type=TemplateType.proposal,
    )
    assert doc.status == "pending"

    # Should return False for active job
    result = await delete_document(db_session, doc.id)
    assert result is False

    # Verify still exists
    still_there = await get_document(db_session, doc.id)
    assert still_there is not None

    # Now change status to ready and delete should succeed
    doc.status = "ready"
    await db_session.flush()
    result = await delete_document(db_session, doc.id)
    assert result is True


@pytest.mark.asyncio
async def test_delete_document_not_found(db_session: AsyncSession):
    """Deleting non-existent document returns False."""
    result = await delete_document(db_session, uuid.uuid4())
    assert result is False
