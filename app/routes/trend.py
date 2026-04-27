"""
Charlie -- GET /trend/{venue_id}
Returns the last N weekly snapshots for Sentinel's trend analysis.
Oldest-to-newest so the agent can read drift direction naturally.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.errors import VenueNotFoundError
from app.models import Venue, WeeklyReport
from app.schemas import MetricDetail, TrendResponse, WeeklySnapshot
from app.routes._venue_lookup import resolve_venue

router = APIRouter(tags=["Trend"])


@router.get("/trend/{venue_id}", response_model=TrendResponse)
async def get_venue_trend(
    venue_id: str,
    weeks: int = Query(default=4, ge=1, le=52, description="Trailing weeks to return. Default 4; use 8+ for longer-cycle patterns."),
    db: AsyncSession = Depends(get_db),
):
    """
    Return the last N weekly snapshots for a venue, ordered oldest to newest.
    Sentinel calls this to detect multi-week metric drift before forecasting.
    Returns however many weeks of history exist if fewer than requested.
    """
    venue = await resolve_venue(db, venue_id)

    reports_result = await db.execute(
        select(WeeklyReport)
        .where(WeeklyReport.venue_id == venue.id)
        .order_by(WeeklyReport.week_ending.desc())
        .limit(weeks)
    )
    reports = list(reports_result.scalars().all())
    reports.reverse()  # oldest first so Sentinel reads the sequence chronologically

    snapshots = [
        WeeklySnapshot(
            week_ending=report.week_ending,
            net_sales=report.nugget_payload["net_sales"],
            prime=MetricDetail(**report.nugget_payload["prime"]),
            labor=MetricDetail(**report.nugget_payload["labor"]),
            food=MetricDetail(**report.nugget_payload["food"]),
            primary_driver=report.nugget_payload["primary_driver"],
        )
        for report in reports
    ]

    return TrendResponse(
        venue_id=str(venue.id),
        venue_name=venue.name,
        weeks=len(snapshots),
        snapshots=snapshots,
    )
