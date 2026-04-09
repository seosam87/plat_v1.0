"""Tests for CRM models: Client, ClientContact, ClientInteraction."""
from __future__ import annotations

import pytest


def test_client_model_exists():
    from app.models.client import Client
    assert Client.__tablename__ == "clients"


def test_client_has_required_columns():
    from app.models.client import Client
    col_names = {c.name for c in Client.__table__.columns}
    required = {
        "id", "company_name", "legal_name", "inn", "kpp",
        "phone", "email", "notes", "manager_id", "is_deleted",
        "created_at", "updated_at",
    }
    assert required.issubset(col_names), f"Missing: {required - col_names}"


def test_client_company_name_indexed():
    from app.models.client import Client
    indexes = {idx.name for idx in Client.__table__.indexes}
    assert any("company_name" in idx for idx in indexes) or \
        Client.__table__.columns["company_name"].index


def test_client_contact_model_exists():
    from app.models.client import ClientContact
    assert ClientContact.__tablename__ == "client_contacts"


def test_client_contact_has_required_columns():
    from app.models.client import ClientContact
    col_names = {c.name for c in ClientContact.__table__.columns}
    required = {
        "id", "client_id", "name", "phone", "email",
        "role", "telegram_username", "notes", "created_at",
    }
    assert required.issubset(col_names), f"Missing: {required - col_names}"


def test_client_interaction_model_exists():
    from app.models.client import ClientInteraction
    assert ClientInteraction.__tablename__ == "client_interactions"


def test_client_interaction_has_required_columns():
    from app.models.client import ClientInteraction
    col_names = {c.name for c in ClientInteraction.__table__.columns}
    required = {
        "id", "client_id", "author_id", "note",
        "interaction_date", "created_at", "updated_at",
    }
    assert required.issubset(col_names), f"Missing: {required - col_names}"


def test_site_has_client_id():
    from app.models.site import Site
    col_names = {c.name for c in Site.__table__.columns}
    assert "client_id" in col_names


def test_models_registered_in_init():
    from app.models import Client, ClientContact, ClientInteraction  # noqa: F401


def test_migration_0043_exists():
    import importlib
    mod = importlib.import_module("alembic.versions.0043_add_crm_tables")
    assert mod.revision == "0043"
    assert mod.down_revision == "0042"
