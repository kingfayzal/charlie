"""
PrimeOps Agentic OS — Entity Resolution Layer (THE MOAT)

Maps external IDs from Toast, 7shifts, MarketMan, etc. to a single Universal Venue ID.
All data MUST pass through resolution before any math happens.

If a mapping is missing, we raise MappingNotFoundError — we never guess.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import SourceMapping, Venue
from app.errors import MappingNotFoundError


async def load_mapping_dict(session: AsyncSession) -> dict[tuple[str, str], str]:
    """
    Load the full mapping table into a dict for fast DataFrame joins.

    Returns:
        {(external_id, source_system) → str(universal_venue_id)}
    """
    result = await session.execute(select(SourceMapping))
    mappings = result.scalars().all()

    return {
        (m.external_id, m.source_system.value): str(m.universal_venue_id)
        for m in mappings
    }


async def load_venue_lookup(session: AsyncSession) -> dict[str, dict]:
    """
    Load all venues into a lookup dict.

    Returns:
        {str(venue_id) → {"name": ..., "target_prime_pct": ..., ...}}
    """
    result = await session.execute(select(Venue))
    venues = result.scalars().all()

    return {
        str(v.id): {
            "name": v.name,
            "target_prime_pct": v.target_prime_pct,
            "target_labor_pct": v.target_labor_pct,
            "target_food_pct": v.target_food_pct,
        }
        for v in venues
    }


def resolve_dataframe(
    df: pd.DataFrame,
    source_system: str,
    mapping_dict: dict[tuple[str, str], str],
) -> pd.DataFrame:
    """
    Add a 'universal_venue_id' column to a DataFrame by resolving external IDs.

    Args:
        df: DataFrame with a 'venue_ext_id' column.
        source_system: The source system (e.g., 'toast', '7shifts').
        mapping_dict: The {(external_id, source) → venue_id} lookup.

    Returns:
        DataFrame with 'universal_venue_id' column added.

    Raises:
        MappingNotFoundError: If any external ID cannot be resolved.
    """
    if "venue_ext_id" not in df.columns:
        raise ValueError(f"DataFrame is missing required column 'venue_ext_id'.")

    # Create a resolution series
    resolved = df["venue_ext_id"].map(
        lambda ext_id: mapping_dict.get((str(ext_id), source_system))
    )

    # Check for unmapped IDs
    unmapped_mask = resolved.isna()
    if unmapped_mask.any():
        unmapped_ids = df.loc[unmapped_mask, "venue_ext_id"].unique().tolist()
        raise MappingNotFoundError(
            external_id=str(unmapped_ids[0]),
            source_system=source_system,
        )

    df = df.copy()
    df["universal_venue_id"] = resolved
    return df
