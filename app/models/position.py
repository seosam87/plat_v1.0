import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class KeywordPosition(Base):
    """Position check record. Table is monthly range-partitioned on checked_at.

    Partition management is handled by migration 0011 which creates
    the parent table with PARTITION BY RANGE and a function to create
    monthly child partitions on demand.
    """

    __tablename__ = "keyword_positions"
    # Partitioned tables in PG require the partition key in the PK
    __table_args__ = {"postgresql_partition_by": "RANGE (checked_at)"}

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    keyword_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("keywords.id", ondelete="CASCADE"),
        nullable=False,
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
    )
    engine: Mapped[str] = mapped_column(String(20), nullable=False)  # "google" | "yandex"
    region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    previous_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delta: Mapped[int | None] = mapped_column(Integer, nullable=True)  # previous - current (positive = improved)
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    clicks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    impressions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ctr: Mapped[float | None] = mapped_column(Float, nullable=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, primary_key=True
    )
