"""
PrimeOps Agentic OS — GET /drilldown/labor/{venue_id}
Returns role-level overtime and hour-vs-schedule data for the Labor Arbitrage Agent.
This is where overtime "bleeds" get exposed.
"""

from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Venue, LaborDrilldown
from app.schemas import LaborDrilldownResponse, RoleDetail
from app.errors import VenueNotFoundError
from app.routes._venue_lookup import resolve_venue


router = APIRouter(tags=["Drilldown"])


@router.get("/drilldown/labor/{venue_id}", response_model=LaborDrilldownResponse)
async def get_labor_drilldown(
    venue_id: str,
    week_ending: Optional[date] = Query(None, description="Week ending date."),
    db: AsyncSession = Depends(get_db),
):
    """
    Return role-level labor detail for a single venue.

    The Labor Arbitrage Agent calls this to:
    - Compare BOH vs FOH hours and costs
    - Identify overtime "bleeds" by role
    - Compare hours_worked vs hours_scheduled to find scheduling drift

    For MVP, returns a template structure. In production, this pulls from
    stored labor data populated by the /ingest pipeline.
    """
    venue = await resolve_venue(db, venue_id)

    # Fetch report
    we_date = week_ending or date.today()
    if week_ending:
        report_result = await db.execute(
            select(LaborDrilldown)
            .where(
                LaborDrilldown.venue_id == venue.id,
                LaborDrilldown.week_ending == week_ending
            )
        )
    else:
        report_result = await db.execute(
            select(LaborDrilldown)
            .where(LaborDrilldown.venue_id == venue.id)
            .order_by(LaborDrilldown.week_ending.desc())
            .limit(1)
        )
    
    report = report_result.scalar_one_or_none()

    if not report:
        return LaborDrilldownResponse(
            venue_id=str(venue.id),
            venue_name=venue.name,
            week_ending=we_date,
            total_labor_cost=0.0,
            total_overtime_cost=0.0,
            overtime_pct_of_labor=0.0,
            boh_summary={
                "total_hours": 0.0,
                "total_overtime": 0.0,
                "total_cost": 0.0,
                "headcount": 0,
            },
            foh_summary={
                "total_hours": 0.0,
                "total_overtime": 0.0,
                "total_cost": 0.0,
                "headcount": 0,
            },
            roles=[],
        )

    payload = report.drilldown_payload
    
    return LaborDrilldownResponse(
        venue_id=str(venue.id),
        venue_name=venue.name,
        week_ending=report.week_ending,
        total_labor_cost=payload["total_labor_cost"],
        total_overtime_cost=payload["total_overtime_cost"],
        overtime_pct_of_labor=payload["overtime_pct_of_labor"],
        boh_summary=payload["boh_summary"],
        foh_summary=payload["foh_summary"],
        roles=[RoleDetail(**r) for r in payload["roles"]],
    )
