"""Service credential storage with per-field Fernet encryption.

Credentials are stored as JSON in service_credentials.credential_data.
Sensitive fields (defined in ENCRYPTED_FIELDS) are encrypted before persist
and decrypted on read.
"""
from __future__ import annotations

import copy
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.service_credential import ServiceCredential
from app.services import crypto_service

# Maps service_name -> list of JSON keys that must be Fernet-encrypted at rest
ENCRYPTED_FIELDS: dict[str, list[str]] = {
    "xmlproxy": ["key"],
    "rucaptcha": ["key"],
}


def save_credential_sync(
    db: Session,
    service_name: str,
    data: dict,
) -> ServiceCredential:
    """Persist credentials for a service, encrypting sensitive fields.

    Args:
        db: Synchronous SQLAlchemy session.
        service_name: Identifier for the external service (e.g. ``"xmlproxy"``).
        data: Plain-text credential dict.

    Returns:
        The persisted :class:`ServiceCredential` instance.
    """
    payload = copy.deepcopy(data)
    for field in ENCRYPTED_FIELDS.get(service_name, []):
        if field in payload and payload[field] is not None:
            payload[field] = crypto_service.encrypt(str(payload[field]))

    credential_data = json.dumps(payload)

    existing = db.execute(
        select(ServiceCredential).where(
            ServiceCredential.service_name == service_name
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.credential_data = credential_data
        db.flush()
        db.commit()
        return existing
    else:
        record = ServiceCredential(
            service_name=service_name,
            credential_data=credential_data,
        )
        db.add(record)
        db.flush()
        db.commit()
        return record


def get_credential_sync(
    db: Session,
    service_name: str,
) -> dict | None:
    """Retrieve and decrypt credentials for a service.

    Args:
        db: Synchronous SQLAlchemy session.
        service_name: Identifier for the external service.

    Returns:
        Plain-text credential dict, or None if not found.
    """
    record = db.execute(
        select(ServiceCredential).where(
            ServiceCredential.service_name == service_name
        )
    ).scalar_one_or_none()

    if record is None or record.credential_data is None:
        return None

    payload = json.loads(record.credential_data)
    for field in ENCRYPTED_FIELDS.get(service_name, []):
        if field in payload and payload[field] is not None:
            payload[field] = crypto_service.decrypt(payload[field])

    return payload
