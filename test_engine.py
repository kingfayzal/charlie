import asyncio
import json
from datetime import date
from app.database import async_session_factory, init_db
from app.engine.adapter import build_clean_data
from app.engine.resolver import load_mapping_dict, load_venue_lookup
from app.engine.cruncher import crunch_weekly_prime
import pandas as pd

async def test_engine():
    # Load sample CSVs
    print("Loading sample data...")
    raw_sales = pd.read_csv("data/pos_daily_sales.csv")
    raw_labor = pd.read_csv("data/labor_summary.csv")
    raw_purchases = pd.read_csv("data/purchases.csv")
    
    print("Running adapter layer...")
    clean = build_clean_data(raw_sales, raw_labor, raw_purchases)
    
    print("Loading entity resolution mappings from database...")
    async with async_session_factory() as db:
        mapping_dict = await load_mapping_dict(db)
        venue_lookup = await load_venue_lookup(db)
        
        print("Crunching Prime Cost metrics...")
        nuggets = crunch_weekly_prime(
            clean,
            mapping_dict,
            venue_lookup,
            date.fromisoformat("2026-03-08")
        )
        
        print("\n=== RESULTS ===")
        for n in nuggets:
            print(f"\nVenue: {n.venue_name}")
            print(f"Net Sales: ${n.net_sales:,.2f}")
            print(f"Prime Cost: {n.prime.actual_pct}% (Target: {n.prime.target_pct}%)")
            print(f"Variance: {n.prime.variance_pct}%")
            print(f"Food Cost: {n.food.actual_pct}% | Labor Cost: {n.labor.actual_pct}%")
            print(f"Primary Driver: {n.primary_driver.upper()}")
            print(f"Detail: {n.driver_detail}")
            print("-" * 40)

if __name__ == "__main__":
    asyncio.run(test_engine())
