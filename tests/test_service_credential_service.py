"""Unit tests for service credential service (encrypt/decrypt round-trip)."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models.service_credential import ServiceCredential  # noqa: F401 — needed for metadata
from app.services.service_credential_service import (
    get_credential_sync,
    save_credential_sync,
)


@pytest.fixture()
def db():
    """In-memory SQLite session with service_credentials table."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine, tables=[ServiceCredential.__table__])
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_save_and_get_roundtrip(db):
    """Credentials for xmlproxy survive a save→get round-trip with key decrypted."""
    save_credential_sync(db, "xmlproxy", {"user": "login", "key": "secret123"})

    result = get_credential_sync(db, "xmlproxy")
    assert result is not None
    assert result["user"] == "login"
    assert result["key"] == "secret123"


def test_key_is_stored_encrypted(db):
    """The 'key' field for xmlproxy must be stored encrypted (not plain-text)."""
    save_credential_sync(db, "xmlproxy", {"user": "login", "key": "mysecret"})

    import json

    record = db.query(ServiceCredential).filter_by(service_name="xmlproxy").first()
    raw = json.loads(record.credential_data)
    # Fernet tokens start with "gAAAAA"
    assert raw["key"] != "mysecret"
    assert raw["key"].startswith("gAAAAA") or len(raw["key"]) > 20


def test_get_nonexistent_service_returns_none(db):
    """Getting credentials for an unknown service name returns None."""
    result = get_credential_sync(db, "nonexistent_service")
    assert result is None


def test_upsert_second_write_wins(db):
    """Saving credentials twice for the same service replaces the first value."""
    save_credential_sync(db, "xmlproxy", {"user": "user1", "key": "key1"})
    save_credential_sync(db, "xmlproxy", {"user": "user2", "key": "key2"})

    result = get_credential_sync(db, "xmlproxy")
    assert result["user"] == "user2"
    assert result["key"] == "key2"


def test_unencrypted_field_passes_through(db):
    """The 'user' field for xmlproxy is NOT in ENCRYPTED_FIELDS — stored as plain text."""
    save_credential_sync(db, "xmlproxy", {"user": "plainuser", "key": "k"})
    result = get_credential_sync(db, "xmlproxy")
    assert result["user"] == "plainuser"
