"""
PrimeOps Agentic OS — GET /drilldown/food/{venue_id}
Returns category and vendor breakdown for food cost.
The Food Cost Agent calls this to identify top-spend categories and vendor anomalies.
"""

from __future__ import annotations

from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import FoodDrilldown, Venue
from app.schemas import CategoryDetail, FoodDrilldownResponse, VendorDetail
from app.errors import VenueNotFoundError
from app.routes._venue_lookup import resolve_venue


router = APIRouter(tags=["Drilldown"])


@router.get("/drilldown/food/{venue_id}", response_model=FoodDrilldownResponse)
async def get_food_drilldown(
    venue_id: str,
    week_ending: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """
    Return category and vendor food cost breakdown for a single venue.
    The Food Cost Agent calls this to identify top spend categories,
    vendor price anomalies, and waste signals.
    """
    venue = await resolve_venue(db, venue_id)

    we_date = week_ending or date.today()

    if week_ending:
        report_result = await db.execute(
            select(FoodDrilldown).where(
                FoodDrilldown.venue_id == venue.id,
                FoodDrilldown.week_ending == week_ending,
            )
        )
    else:
        report_result = await db.execute(
            select(FoodDrilldown)
            .where(FoodDrilldown.venue_id == venue.id)
            .order_by(FoodDrilldown.week_ending.desc())
            .limit(1)
        )

    report = report_result.scalar_one_or_none()

    if not report:
        return FoodDrilldownResponse(
            venue_id=str(venue.id),
            venue_name=venue.name,
            week_ending=we_date,
            total_food_cost=0.0,
            food_pct=0.0,
            target_food_pct=round(venue.target_food_pct * 100, 1),
            variance_pct=0.0,
            categories=[],
            vendors=[],
        )

    payload = report.drilldown_payload
    return FoodDrilldownResponse(
        venue_id=str(venue.id),
        venue_name=venue.name,
        week_ending=report.week_ending,
        total_food_cost=payload["total_food_cost"],
        food_pct=payload["food_pct"],
        target_food_pct=payload["target_food_pct"],
        variance_pct=payload["variance_pct"],
        categories=[CategoryDetail(**c) for c in payload["categories"]],
        vendors=[VendorDetail(**v) for v in payload["vendors"]],
    )
