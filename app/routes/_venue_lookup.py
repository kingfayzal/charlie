"""Helper for resolving a venue from either a UUID string or a (partial) name.

Used by all `/<route>/{venue_id}` endpoints so the agents can pass a
human-readable venue name (e.g. "Central Ave") and still get a clean lookup
instead of a 500 from `UUID(venue_id)`.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.errors import VenueNotFoundError
from app.models import Venue


async def resolve_venue(db: AsyncSession, venue_id_or_name: str) -> Venue:
    """Return the Venue row matching either a UUID or a (partial) name.

    Order of resolution:
      1. If the string parses as a UUID -> direct ID lookup.
      2. Otherwise, exact case-insensitive name match.
      3. Otherwise, case-insensitive substring match (e.g. "central avenue"
         resolves to "Central Ave"; "river" resolves to "Riverside").

    Raises VenueNotFoundError if nothing matches.
    """
    candidate = (venue_id_or_name or "").strip()

    # 1. UUID path
    try:
        uid = UUID(candidate)
        result = await db.execute(select(Venue).where(Venue.id == uid))
        venue = result.scalar_one_or_none()
        if venue:
            return venue
    except (ValueError, AttributeError):
        pass

    # 2 + 3. Name-based lookup (case-insensitive)
    result = await db.execute(select(Venue))
    venues = list(result.scalars().all())

    lowered = candidate.lower()
    for venue in venues:
        if venue.name.lower() == lowered:
            return venue

    for venue in venues:
        name_lower = venue.name.lower()
        if lowered and (lowered in name_lower or name_lower in lowered):
            return venue

    raise VenueNotFoundError(candidate)
