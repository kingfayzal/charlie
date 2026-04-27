"""
PrimeOps Agentic OS — GET /brief/{venue_id}
Returns the weekly variance summary (Nugget JSON) for the Quant Agent.
This is the primary endpoint the Quant Agent calls to get its "briefing."
"""

from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import OperationalContext, Venue, WeeklyReport
from app.schemas import BriefResponse, MetricDetail
from app.errors import VenueNotFoundError
from app.routes._venue_lookup import resolve_venue


router = APIRouter(tags=["Brief"])


@router.get("/brief/{venue_id}", response_model=BriefResponse)
async def get_venue_brief(
    venue_id: str,
    week_ending: Optional[date] = Query(None, description="Week ending date. Defaults to most recent."),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the weekly variance summary for a single venue.

    The Quant Agent calls this to get its "briefing" before generating
    operator-facing narratives. Includes recent context notes so the agent
    can account for operational context (e.g., "New chef training").

    For MVP, this returns mock/computed data. In production, it would query
    a weekly_reports table populated by the /ingest endpoint.
    """
    venue = await resolve_venue(db, venue_id)

    # Fetch recent context notes (last 5)
    notes_result = await db.execute(
        select(OperationalContext)
        .where(OperationalContext.venue_id == venue.id)
        .order_by(OperationalContext.created_at.desc())
        .limit(5)
    )
    notes = [n.note for n in notes_result.scalars().all()]

    # Fetch report
    we_date = week_ending or date.today()
    if week_ending:
        report_result = await db.execute(
            select(WeeklyReport)
            .where(
                WeeklyReport.venue_id == venue.id,
                WeeklyReport.week_ending == week_ending
            )
        )
    else:
        report_result = await db.execute(
            select(WeeklyReport)
            .where(WeeklyReport.venue_id == venue.id)
            .order_by(WeeklyReport.week_ending.desc())
            .limit(1)
        )
    
    report = report_result.scalar_one_or_none()

    if not report:
        target_labor = venue.target_labor_pct
        target_food = venue.target_food_pct
        target_prime = venue.target_prime_pct

        return BriefResponse(
            venue_id=str(venue.id),
            venue_name=venue.name,
            week_ending=we_date,
            net_sales=0.0,  # Populated after /ingest runs
            prime=MetricDetail(
                actual_pct=0.0,
                target_pct=round(target_prime * 100, 1),
                variance_pct=0.0,
                actual_cost=0.0,
            ),
            labor=MetricDetail(
                actual_pct=0.0,
                target_pct=round(target_labor * 100, 1),
                variance_pct=0.0,
                actual_cost=0.0,
            ),
            food=MetricDetail(
                actual_pct=0.0,
                target_pct=round(target_food * 100, 1),
                variance_pct=0.0,
                actual_cost=0.0,
            ),
            primary_driver="none",
            driver_detail="No data ingested yet for this period. Run /ingest first.",
            context_notes=notes,
        )

    payload = report.nugget_payload
    
    return BriefResponse(
        venue_id=str(venue.id),
        venue_name=venue.name,
        week_ending=report.week_ending,
        net_sales=payload["net_sales"],
        prime=MetricDetail(**payload["prime"]),
        labor=MetricDetail(**payload["labor"]),
        food=MetricDetail(**payload["food"]),
        primary_driver=payload["primary_driver"],
        driver_detail=payload["driver_detail"],
        context_notes=notes,
    )
