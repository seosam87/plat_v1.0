"""add keyword_positions partitioned table + partition management

Revision ID: 0011
Revises: 0010
Create Date: 2026-04-01

CRITICAL: This table MUST be partitioned before any data is written.
Monthly range partitioning on checked_at. 50 sites × 500 kw × 2 engines
× 365 days = 18M rows/year — non-partitioned table causes full scans.
"""
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create partitioned parent table via raw SQL
    # SQLAlchemy/Alembic don't natively handle PARTITION BY in create_table
    op.execute("""
        CREATE TABLE keyword_positions (
            id UUID NOT NULL,
            keyword_id UUID NOT NULL REFERENCES keywords(id) ON DELETE CASCADE,
            site_id UUID NOT NULL REFERENCES sites(id) ON DELETE CASCADE,
            engine VARCHAR(20) NOT NULL,
            region VARCHAR(100),
            position INTEGER,
            previous_position INTEGER,
            delta INTEGER,
            url VARCHAR(2000),
            clicks INTEGER,
            impressions INTEGER,
            ctr DOUBLE PRECISION,
            checked_at TIMESTAMPTZ NOT NULL,
            PRIMARY KEY (id, checked_at)
        ) PARTITION BY RANGE (checked_at)
    """)

    # Indexes on the parent (inherited by partitions)
    op.execute("""
        CREATE INDEX ix_kp_keyword_engine_date
        ON keyword_positions (keyword_id, engine, checked_at DESC)
    """)
    op.execute("""
        CREATE INDEX ix_kp_site_date
        ON keyword_positions (site_id, checked_at DESC)
    """)

    # Create a default partition for any data outside known ranges
    op.execute("""
        CREATE TABLE keyword_positions_default
        PARTITION OF keyword_positions DEFAULT
    """)

    # Function to create monthly partitions on demand
    op.execute("""
        CREATE OR REPLACE FUNCTION create_kp_partition(target_date DATE)
        RETURNS TEXT AS $$
        DECLARE
            partition_name TEXT;
            start_date DATE;
            end_date DATE;
        BEGIN
            start_date := date_trunc('month', target_date)::DATE;
            end_date := (start_date + INTERVAL '1 month')::DATE;
            partition_name := 'keyword_positions_' || to_char(start_date, 'YYYY_MM');

            -- Check if partition already exists
            IF NOT EXISTS (
                SELECT 1 FROM pg_class WHERE relname = partition_name
            ) THEN
                EXECUTE format(
                    'CREATE TABLE %I PARTITION OF keyword_positions
                     FOR VALUES FROM (%L) TO (%L)',
                    partition_name, start_date, end_date
                );
            END IF;

            RETURN partition_name;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Pre-create partitions for current and next 3 months
    op.execute("""
        SELECT create_kp_partition(CURRENT_DATE);
        SELECT create_kp_partition(CURRENT_DATE + INTERVAL '1 month');
        SELECT create_kp_partition(CURRENT_DATE + INTERVAL '2 months');
        SELECT create_kp_partition(CURRENT_DATE + INTERVAL '3 months');
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS create_kp_partition(DATE)")
    op.execute("DROP TABLE IF EXISTS keyword_positions CASCADE")
