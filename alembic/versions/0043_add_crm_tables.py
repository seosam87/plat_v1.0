"""Phase 20: add CRM tables (clients, client_contacts, client_interactions) and sites.client_id FK.

Revision ID: 0043
Revises: 0042
Create Date: 2026-04-09
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create clients table first (parent)
    op.create_table(
        "clients",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("legal_name", sa.String(255), nullable=True),
        sa.Column("inn", sa.String(20), nullable=True),
        sa.Column("kpp", sa.String(20), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "manager_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index("ix_clients_company_name", "clients", ["company_name"])
    op.create_index("ix_clients_manager_id", "clients", ["manager_id"])

    # 2. Create client_contacts table
    op.create_table(
        "client_contacts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "client_id",
            UUID(as_uuid=True),
            sa.ForeignKey("clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("role", sa.String(100), nullable=True),
        sa.Column("telegram_username", sa.String(100), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index(
        "ix_client_contacts_client_id", "client_contacts", ["client_id"]
    )

    # 3. Create client_interactions table
    op.create_table(
        "client_interactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "client_id",
            UUID(as_uuid=True),
            sa.ForeignKey("clients.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column(
            "interaction_date",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
    )

    op.create_index(
        "ix_client_interactions_client_id_date",
        "client_interactions",
        ["client_id", sa.text("interaction_date DESC")],
    )

    # 4. Add client_id FK to sites table (last)
    op.add_column(
        "sites",
        sa.Column(
            "client_id",
            UUID(as_uuid=True),
            sa.ForeignKey("clients.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_sites_client_id", "sites", ["client_id"])


def downgrade() -> None:
    # Reverse order
    op.drop_index("ix_sites_client_id", table_name="sites")
    op.drop_column("sites", "client_id")

    op.drop_index(
        "ix_client_interactions_client_id_date",
        table_name="client_interactions",
    )
    op.drop_table("client_interactions")

    op.drop_index("ix_client_contacts_client_id", table_name="client_contacts")
    op.drop_table("client_contacts")

    op.drop_index("ix_clients_manager_id", table_name="clients")
    op.drop_index("ix_clients_company_name", table_name="clients")
    op.drop_table("clients")
