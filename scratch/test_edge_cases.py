import asyncio
import pandas as pd
from datetime import date
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models import Base
from app.database import engine, async_session_factory
from app.engine.adapter import build_clean_data
from app.engine.resolver import load_mapping_dict, load_venue_lookup, MappingNotFoundError
from app.engine.cruncher import crunch_weekly_prime, DataReadinessError

async def test_mapping_not_found():
    print("\n--- Test: Mapping Not Found ---")
    async with async_session_factory() as session:
        mapping_dict = await load_mapping_dict(session)
        venue_lookup = await load_venue_lookup(session)

    # Create dummy data with unknown venue_ext_id
    sales_df = pd.DataFrame([{"venue_ext_id": "unknown_toast_id", "date": "2024-01-01", "net_sales": 1000.0}])
    labor_df = pd.DataFrame([{"venue_ext_id": "unknown_7shifts_id", "week_ending": "2024-01-07", "actual_labor_cost": 150.0, "line_cook_hours": 10.0}])
    purchases_df = pd.DataFrame([{"venue_ext_id": "unknown_mm_id", "date": "2024-01-01", "invoice_total": 200.0}])

    clean = build_clean_data(sales_df, labor_df, purchases_df)
    
    try:
        nuggets = crunch_weekly_prime(
            clean, mapping_dict, venue_lookup, date(2024, 1, 7)
        )
        print("FAIL: Expected MappingNotFoundError but it succeeded.")
    except MappingNotFoundError as e:
        print(f"PASS: Caught MappingNotFoundError - {e}")
    except Exception as e:
        print(f"FAIL: Caught wrong exception: {e}")

async def test_data_readiness_error():
    print("\n--- Test: Data Readiness Error (Missing columns) ---")
    async with async_session_factory() as session:
        mapping_dict = await load_mapping_dict(session)
        venue_lookup = await load_venue_lookup(session)

    # Valid ID based on seed_db.py: Toast "Downtown", 7shifts "Downtown", MarketMan "downtown_hub"
    sales_df = pd.DataFrame([{"venue_ext_id": "Downtown", "date": "2024-01-01", "net_sales": 1000.0}])
    # Missing the venue in labor data completely
    labor_df = pd.DataFrame([{"venue_ext_id": "Central Ave", "week_ending": "2024-01-07", "actual_labor_cost": 500}]) 
    purchases_df = pd.DataFrame([{"venue_ext_id": "downtown_hub", "date": "2024-01-01", "invoice_total": 200.0}])

    # Note: build_clean_data will pass because the format is correct.
    clean = build_clean_data(sales_df, labor_df, purchases_df)
    
    try:
        # It should fail here because 'Downtown' has sales & purchases but no labor after resolution
        nuggets = crunch_weekly_prime(
            clean, mapping_dict, venue_lookup, date(2024, 1, 7)
        )
        print("FAIL: Expected DataReadinessError but it succeeded.")
    except DataReadinessError as e:
        print(f"PASS: Caught DataReadinessError - {e.missing_sources}")
    except Exception as e:
        print(f"FAIL: Caught wrong exception: {e}")

async def test_zero_sales():
    print("\n--- Test: Zero Sales (Divide by Zero check) ---")
    async with async_session_factory() as session:
        mapping_dict = await load_mapping_dict(session)
        venue_lookup = await load_venue_lookup(session)

    # Net sales is 0.0
    sales_df = pd.DataFrame([{"venue_ext_id": "Downtown", "date": "2024-01-01", "net_sales": 0.0}])
    labor_df = pd.DataFrame([{"venue_ext_id": "Downtown", "week_ending": "2024-01-07", "actual_labor_cost": 150.0, "line_cook_hours": 10.0}])
    purchases_df = pd.DataFrame([{"venue_ext_id": "downtown_hub", "date": "2024-01-01", "invoice_total": 200.0}])

    clean = build_clean_data(sales_df, labor_df, purchases_df)
    
    try:
        nuggets = crunch_weekly_prime(
            clean, mapping_dict, venue_lookup, date(2024, 1, 7)
        )
        print("PASS: Computed without crashing.")
        for n in nuggets:
            print(f"  Venue: {n.venue_name}")
            print(f"  Sales: {n.net_sales}")
            print(f"  Prime Cost Pct: {n.prime.actual_pct} (Expected 0.0 or handled gracefully)")
    except Exception as e:
        print(f"FAIL: Caught exception: {e}")

async def main():
    await test_mapping_not_found()
    await test_data_readiness_error()
    await test_zero_sales()

if __name__ == "__main__":
    asyncio.run(main())
