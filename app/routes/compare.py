"""
PrimeOps Agentic OS — GET /compare/venues
Returns all venues' weekly metrics side-by-side, ranked by Prime Cost performance.
The Multi-Venue Benchmark Agent calls this to identify best/worst performers.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import WeeklyReport
from app.schemas import CompareVenuesResponse, MetricDetail, VenueComparisonRow


router = APIRouter(tags=["Compare"])


@router.get("/compare/venues", response_model=CompareVenuesResponse)
async def compare_venues(
    week_ending: Optional[date] = Query(None, description="Week to compare. Defaults to most recent."),
    db: AsyncSession = Depends(get_db),
):
    """
    Return all venues' Prime Cost metrics for a single week, ranked by performance.
    Rank 1 = lowest (best) prime cost variance.
    """
    if week_ending:
        result = await db.execute(
            select(WeeklyReport).where(WeeklyReport.week_ending == week_ending)
        )
    else:
        # Most recent week that has data
        subq_result = await db.execute(
            select(WeeklyReport.week_ending)
            .order_by(WeeklyReport.week_ending.desc())
            .limit(1)
        )
        latest_week = subq_result.scalar_one_or_none()
        if not latest_week:
            return CompareVenuesResponse(week_ending=week_ending or date.today(), count=0, venues=[])

        result = await db.execute(
            select(WeeklyReport).where(WeeklyReport.week_ending == latest_week)
        )
        week_ending = latest_week

    reports = result.scalars().all()
    if not reports:
        return CompareVenuesResponse(week_ending=week_ending or date.today(), count=0, venues=[])

    rows: list[VenueComparisonRow] = []
    for report in reports:
        p = report.nugget_payload
        rows.append(VenueComparisonRow(
            venue_id=p["venue_id"],
            venue_name=p["venue_name"],
            net_sales=p["net_sales"],
            prime=MetricDetail(**p["prime"]),
            labor=MetricDetail(**p["labor"]),
            food=MetricDetail(**p["food"]),
            rank=0,  # assigned below
        ))

    # Rank by prime cost variance ascending (lower variance = better rank)
    rows.sort(key=lambda r: r.prime.variance_pct)
    for i, row in enumerate(rows):
        row.rank = i + 1

    return CompareVenuesResponse(
        week_ending=week_ending,
        count=len(rows),
        venues=rows,
    )
