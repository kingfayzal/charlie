"""
PrimeOps Agentic OS — GET /venues
Lists all venues with IDs and targets. Used by the Concierge Agent to
resolve venue names to UUIDs from user messages.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Venue
from app.schemas import VenueListResponse, VenueSummary


router = APIRouter(tags=["Venues"])


@router.get("/venues", response_model=VenueListResponse)
async def list_venues(db: AsyncSession = Depends(get_db)):
    """List all venues — used by agents to resolve names to UUIDs."""
    result = await db.execute(select(Venue).order_by(Venue.name))
    venues = result.scalars().all()

    return VenueListResponse(venues=[
        VenueSummary(
            id=str(v.id),
            name=v.name,
            target_prime_pct=round(v.target_prime_pct * 100, 1),
            target_labor_pct=round(v.target_labor_pct * 100, 1),
            target_food_pct=round(v.target_food_pct * 100, 1),
        )
        for v in venues
    ])
