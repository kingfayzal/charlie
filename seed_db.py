"""
PrimeOps Agentic OS — Database Seed Script

Seeds the local SQLite database with:
  - 3 Venues (Central Ave, Riverside, Downtown) with operator targets
  - 9 Source Mappings (3 per venue: Toast, 7shifts, MarketMan)

Entity Resolution Mappings (from operator spec):
  - heathfield    → Central Ave   (MarketMan)
  - 3t0862        → Riverside     (MarketMan)
  - downtown_hub  → Downtown      (MarketMan)
  - Venue names used directly for Toast (POS) and 7shifts (Labor)

Usage:
  cd Neo
  python seed_db.py
"""

import asyncio
import uuid
from app.database import async_session_factory, init_db
from app.models import Venue, SourceMapping, SourceSystem


# ---------------------------------------------------------------------------
# Venue Definitions
# ---------------------------------------------------------------------------
VENUES = [
    {
        "id": uuid.UUID("11111111-1111-1111-1111-111111111111"),
        "name": "Central Ave",
        "target_prime_pct": 0.58,
        "target_labor_pct": 0.30,
        "target_food_pct": 0.28,
    },
    {
        "id": uuid.UUID("22222222-2222-2222-2222-222222222222"),
        "name": "Riverside",
        "target_prime_pct": 0.60,
        "target_labor_pct": 0.32,
        "target_food_pct": 0.28,
    },
    {
        "id": uuid.UUID("33333333-3333-3333-3333-333333333333"),
        "name": "Downtown",
        "target_prime_pct": 0.60,
        "target_labor_pct": 0.30,
        "target_food_pct": 0.30,
    },
]

# ---------------------------------------------------------------------------
# Source Mappings — The Entity Resolution Cross-Walk
# ---------------------------------------------------------------------------
MAPPINGS = [
    # --- Central Ave ---
    # Toast POS: uses venue name "Central Ave"
    {"external_id": "Central Ave", "source_system": SourceSystem.TOAST,
     "universal_venue_id": uuid.UUID("11111111-1111-1111-1111-111111111111")},
    # 7shifts Labor: uses venue name "Central Ave"
    {"external_id": "Central Ave", "source_system": SourceSystem.SEVEN_SHIFTS,
     "universal_venue_id": uuid.UUID("11111111-1111-1111-1111-111111111111")},
    # MarketMan Purchases: uses external ID "heathfield"
    {"external_id": "heathfield", "source_system": SourceSystem.MARKETMAN,
     "universal_venue_id": uuid.UUID("11111111-1111-1111-1111-111111111111")},

    # --- Riverside ---
    {"external_id": "Riverside", "source_system": SourceSystem.TOAST,
     "universal_venue_id": uuid.UUID("22222222-2222-2222-2222-222222222222")},
    {"external_id": "Riverside", "source_system": SourceSystem.SEVEN_SHIFTS,
     "universal_venue_id": uuid.UUID("22222222-2222-2222-2222-222222222222")},
    {"external_id": "3t0862", "source_system": SourceSystem.MARKETMAN,
     "universal_venue_id": uuid.UUID("22222222-2222-2222-2222-222222222222")},

    # --- Downtown ---
    {"external_id": "Downtown", "source_system": SourceSystem.TOAST,
     "universal_venue_id": uuid.UUID("33333333-3333-3333-3333-333333333333")},
    {"external_id": "Downtown", "source_system": SourceSystem.SEVEN_SHIFTS,
     "universal_venue_id": uuid.UUID("33333333-3333-3333-3333-333333333333")},
    {"external_id": "downtown_hub", "source_system": SourceSystem.MARKETMAN,
     "universal_venue_id": uuid.UUID("33333333-3333-3333-3333-333333333333")},
]


async def seed():
    """Create tables and insert seed data."""
    await init_db()
    print("✓ Tables created.")

    async with async_session_factory() as session:
        # Seed Venues
        for v_data in VENUES:
            venue = Venue(**v_data)
            session.add(venue)
        await session.flush()
        print(f"✓ {len(VENUES)} venues seeded.")

        # Seed Mappings
        for m_data in MAPPINGS:
            mapping = SourceMapping(**m_data)
            session.add(mapping)
        await session.flush()
        print(f"✓ {len(MAPPINGS)} source mappings seeded.")

        await session.commit()
        print("✓ Database seeded successfully.")

    # Print summary
    print("\n--- Entity Resolution Map ---")
    for m in MAPPINGS:
        venue_name = next(v["name"] for v in VENUES if v["id"] == m["universal_venue_id"])
        print(f"  {m['source_system'].value:12s} | {m['external_id']:15s} → {venue_name}")


if __name__ == "__main__":
    asyncio.run(seed())
