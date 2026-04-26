"""
PrimeOps Agentic OS — Pydantic Schemas
Request/Response DTOs for the FastAPI endpoints.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Ingest
# ---------------------------------------------------------------------------
class IngestRequest(BaseModel):
    """POST /ingest — file paths for the three data sources (GCS or local)."""
    sales_path: str = Field(..., description="Path to sales CSV (gs:// or local)")
    labor_path: str = Field(..., description="Path to labor CSV")
    purchases_path: str = Field(..., description="Path to purchases CSV")
    week_ending: date = Field(..., description="The Saturday that ends the reporting week")


# ---------------------------------------------------------------------------
# Nugget JSON — core output format
# ---------------------------------------------------------------------------
class MetricDetail(BaseModel):
    actual_pct: float = Field(..., description="Actual percentage (e.g., 32.1 = 32.1%)")
    target_pct: float = Field(..., description="Operator-defined target percentage")
    variance_pct: float = Field(..., description="Actual - Target. Positive = over target.")
    actual_cost: float = Field(..., description="Absolute dollar amount")


class DataQuality(BaseModel):
    status: str = Field(..., description="'complete' or 'partial'")
    missing_sources: list[str] = Field(default_factory=list)
    missing_days: list[str] = Field(default_factory=list)


class NuggetJSON(BaseModel):
    """Self-contained weekly performance snapshot for one venue."""
    venue_id: str
    venue_name: str
    week_ending: date

    net_sales: float

    labor: MetricDetail
    food: MetricDetail
    prime: MetricDetail

    primary_driver: str = Field(..., description="'labor' or 'food'")
    driver_detail: str

    data_quality: DataQuality


class NuggetResponse(BaseModel):
    count: int
    week_ending: date
    nuggets: list[NuggetJSON]


# ---------------------------------------------------------------------------
# Brief — weekly variance summary for the Quant Agent
# ---------------------------------------------------------------------------
class BriefResponse(BaseModel):
    venue_id: str
    venue_name: str
    week_ending: date
    net_sales: float
    prime: MetricDetail
    labor: MetricDetail
    food: MetricDetail
    primary_driver: str
    driver_detail: str
    context_notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Labor Drilldown
# ---------------------------------------------------------------------------
class RoleDetail(BaseModel):
    role: str
    role_type: str = Field(..., description="BOH, FOH, or MGT")
    headcount: int
    hours_scheduled: float
    hours_worked: float
    hours_variance: float
    overtime_hours: float
    overtime_cost: float
    total_cost: float


class LaborDrilldownResponse(BaseModel):
    venue_id: str
    venue_name: str
    week_ending: date
    total_labor_cost: float
    total_overtime_cost: float
    overtime_pct_of_labor: float
    boh_summary: dict
    foh_summary: dict
    roles: list[RoleDetail]


# ---------------------------------------------------------------------------
# Food Cost Drilldown
# ---------------------------------------------------------------------------
class CategoryDetail(BaseModel):
    category: str
    total_cost: float
    pct_of_food_spend: float = Field(..., description="% of total food spend this week")


class VendorDetail(BaseModel):
    vendor: str
    total_cost: float
    invoice_count: int
    pct_of_food_spend: float


class FoodDrilldownResponse(BaseModel):
    venue_id: str
    venue_name: str
    week_ending: date
    total_food_cost: float
    food_pct: float = Field(..., description="Actual food cost % of net sales")
    target_food_pct: float
    variance_pct: float = Field(..., description="Actual - Target in pp")
    categories: list[CategoryDetail]
    vendors: list[VendorDetail]


# ---------------------------------------------------------------------------
# Venue List
# ---------------------------------------------------------------------------
class VenueSummary(BaseModel):
    id: str
    name: str
    target_prime_pct: float
    target_labor_pct: float
    target_food_pct: float


class VenueListResponse(BaseModel):
    venues: list[VenueSummary]


# ---------------------------------------------------------------------------
# Cross-Venue Comparison
# ---------------------------------------------------------------------------
class VenueComparisonRow(BaseModel):
    venue_id: str
    venue_name: str
    net_sales: float
    prime: MetricDetail
    labor: MetricDetail
    food: MetricDetail
    rank: int = Field(..., description="1 = best prime cost performance (lowest variance)")


class CompareVenuesResponse(BaseModel):
    week_ending: date
    count: int
    venues: list[VenueComparisonRow]


# ---------------------------------------------------------------------------
# Context Notes
# ---------------------------------------------------------------------------
class ContextNoteRequest(BaseModel):
    note: str = Field(..., min_length=1, max_length=2000)
    author: str = Field(default="system")


class ContextNoteResponse(BaseModel):
    id: str
    venue_id: str
    note: str
    author: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Error Responses
# ---------------------------------------------------------------------------
class DataReadinessErrorResponse(BaseModel):
    error: str = "data_readiness_error"
    venue_name: str
    detail: str
    missing_sources: list[str] = Field(default_factory=list)
    missing_days: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str = Field(..., description="User message")
    session_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Client-generated session UUID for conversation continuity",
    )
    venue_id: Optional[str] = Field(
        default=None,
        description="Currently selected venue UUID from the dashboard (optional context hint)",
    )


class ChatResponse(BaseModel):
    reply: str
    agent_name: str = Field(default="assistant", description="Which agent produced this reply")
