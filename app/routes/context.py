"""
PrimeOps Agentic OS — PATCH /context/{venue_id}
Allows ADK agents (or operators) to save operational context notes to the database.
This is the "persistent memory" layer — agents can store observations that
influence future reasoning cycles.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import OperationalContext, Venue
from app.schemas import ContextNoteRequest, ContextNoteResponse
from app.errors import VenueNotFoundError
from app.routes._venue_lookup import resolve_venue


router = APIRouter(tags=["Context"])


@router.patch("/context/{venue_id}", response_model=ContextNoteResponse)
async def save_context_note(
    venue_id: str,
    request: ContextNoteRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Save an operational context note for a venue.

    Agents use this to persist observations that should influence future analysis.
    Examples:
    - "New chef started training on Monday — expect food cost spike."
    - "Patio closed for renovation — 20% fewer covers expected."
    - "Sunday brunch launched — labor targets may need adjustment."

    The Quant Agent reads these notes via /brief/{venue_id} to contextualize
    its variance analysis.
    """
    venue = await resolve_venue(db, venue_id)

    # Create context note
    note = OperationalContext(
        venue_id=venue.id,
        note=request.note,
        author=request.author,
    )
    db.add(note)
    await db.flush()  # Get the generated ID before commit
    await db.refresh(note)

    return ContextNoteResponse(
        id=str(note.id),
        venue_id=str(note.venue_id),
        note=note.note,
        author=note.author,
        created_at=note.created_at,
    )
