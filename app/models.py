"""
PrimeOps Agentic OS — SQLAlchemy ORM Models
The Entity Resolution Layer: venues, source mappings, and operational context.

Business Rules (from CONTEXT.md):
  - Net Sales is the denominator for all percentages.
  - Prime Cost = (Actual Labor Cost + Actual Food Purchases) / Net Sales.
  - Entity Resolution: missing venue mapping → DataReadinessError, never partial calcs.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
import enum


class SourceSystem(str, enum.Enum):
    """Supported external source systems for entity resolution."""
    TOAST = "toast"
    SEVEN_SHIFTS = "7shifts"
    MARKETMAN = "marketman"
    SQUARE = "square"
    CLOVER = "clover"


# ---------------------------------------------------------------------------
# Venue — Universal venue profiles with operator-defined targets
# ---------------------------------------------------------------------------
class Venue(Base):
    __tablename__ = "venues"

    id = Column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Universal Venue ID — the single source of truth across all systems.",
    )
    name = Column(String(255), nullable=False, index=True)

    # Operator-defined targets (percentages as decimals, e.g., 0.30 = 30%)
    target_prime_pct = Column(
        Float, nullable=False, default=0.60,
        comment="Target Prime Cost % (labor + food) / net sales.",
    )
    target_labor_pct = Column(
        Float, nullable=False, default=0.30,
        comment="Target Labor Cost % of net sales.",
    )
    target_food_pct = Column(
        Float, nullable=False, default=0.28,
        comment="Target Food Cost % of net sales.",
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    mappings = relationship("SourceMapping", back_populates="venue", cascade="all, delete-orphan")
    context_notes = relationship("OperationalContext", back_populates="venue", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Venue(id={self.id}, name='{self.name}', prime_target={self.target_prime_pct:.0%})>"


# ---------------------------------------------------------------------------
# SourceMapping — The Entity Resolution Cross-Walk (THE MOAT)
# ---------------------------------------------------------------------------
class SourceMapping(Base):
    __tablename__ = "mappings"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    external_id = Column(
        String(255), nullable=False, index=True,
        comment="The venue/location ID as it exists in the external system.",
    )
    source_system = Column(
        Enum(SourceSystem, name="source_system_enum", create_constraint=True),
        nullable=False,
        comment="Which external system this ID belongs to (toast, 7shifts, etc.).",
    )
    universal_venue_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("venues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="FK to the universal venue this external ID resolves to.",
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    venue = relationship("Venue", back_populates="mappings")

    # Constraints: one external_id per source system
    __table_args__ = (
        UniqueConstraint("external_id", "source_system", name="uq_external_source"),
    )

    def __repr__(self) -> str:
        return f"<SourceMapping({self.source_system.value}:{self.external_id} → {self.universal_venue_id})>"


# ---------------------------------------------------------------------------
# OperationalContext — Persistent memory for venue-level agent notes
# ---------------------------------------------------------------------------
class OperationalContext(Base):
    __tablename__ = "operational_context"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)

    venue_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("venues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    note = Column(
        Text, nullable=False,
        comment="Context note (e.g., 'New chef training', 'Patio closed for renovation').",
    )
    author = Column(
        String(100), nullable=False, default="system",
        comment="Who created this note: 'quant_agent', 'labor_agent', 'operator', etc.",
    )
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    venue = relationship("Venue", back_populates="context_notes")

    def __repr__(self) -> str:
        return f"<OperationalContext(venue={self.venue_id}, note='{self.note[:40]}...')>"


# ---------------------------------------------------------------------------
# WeeklyReport — Persisted outputs from the Cruncher (NuggetJSON)
# ---------------------------------------------------------------------------
from sqlalchemy import Date, JSON

class WeeklyReport(Base):
    __tablename__ = "weekly_reports"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venue_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("venues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    week_ending = Column(Date, nullable=False, index=True)
    
    # Store the entire NuggetJSON payload for easy retrieval
    nugget_payload = Column(JSON, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    venue = relationship("Venue")

    __table_args__ = (
        UniqueConstraint("venue_id", "week_ending", name="uq_venue_week"),
    )

    def __repr__(self) -> str:
        return f"<WeeklyReport(venue={self.venue_id}, week_ending={self.week_ending})>"


# ---------------------------------------------------------------------------
# LaborDrilldown — Persisted role-level drilldown outputs
# ---------------------------------------------------------------------------
class LaborDrilldown(Base):
    __tablename__ = "labor_drilldowns"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venue_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("venues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    week_ending = Column(Date, nullable=False, index=True)
    
    # Store the entire LaborDrilldownResponse payload
    drilldown_payload = Column(JSON, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    venue = relationship("Venue")

    __table_args__ = (
        UniqueConstraint("venue_id", "week_ending", name="uq_venue_week_drilldown"),
    )

    def __repr__(self) -> str:
        return f"<LaborDrilldown(venue={self.venue_id}, week_ending={self.week_ending})>"


# ---------------------------------------------------------------------------
# FoodDrilldown — Persisted category/vendor breakdown outputs
# ---------------------------------------------------------------------------
class FoodDrilldown(Base):
    __tablename__ = "food_drilldowns"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    venue_id = Column(
        Uuid(as_uuid=True),
        ForeignKey("venues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    week_ending = Column(Date, nullable=False, index=True)
    drilldown_payload = Column(JSON, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    venue = relationship("Venue")

    __table_args__ = (
        UniqueConstraint("venue_id", "week_ending", name="uq_venue_week_food_drilldown"),
    )

    def __repr__(self) -> str:
        return f"<FoodDrilldown(venue={self.venue_id}, week_ending={self.week_ending})>"

