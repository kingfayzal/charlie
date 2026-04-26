"""
PrimeOps Agentic OS — POST /ingest
Receives file paths (GCS or local), runs the full adapter → cruncher pipeline.

Resolution happens exactly once here, then pre-resolved DataFrames are passed
to the cruncher and all drilldown builders.
"""

from __future__ import annotations

import asyncio
import io
from datetime import date

import pandas as pd
from fastapi import APIRouter, Depends
from sqlalchemy import delete, and_
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from app.database import get_db
from app.schemas import IngestRequest, NuggetJSON, NuggetResponse
from app.engine.adapter import build_clean_data
from app.engine.resolver import load_mapping_dict, load_venue_lookup, resolve_dataframe
from app.engine.cruncher import crunch_weekly_prime, build_labor_drilldown, build_food_drilldown
from app.models import WeeklyReport, LaborDrilldown, FoodDrilldown


router = APIRouter(tags=["Ingest"])


def _load_csv(path: str) -> pd.DataFrame:
    if path.startswith("gs://"):
        from google.cloud import storage
        parts = path.replace("gs://", "").split("/", 1)
        client = storage.Client()
        blob = client.bucket(parts[0]).blob(parts[1] if len(parts) > 1 else "")
        return pd.read_csv(io.StringIO(blob.download_as_text()))
    return pd.read_csv(path)


@router.post("/ingest", response_model=NuggetResponse)
async def ingest_data(request: IngestRequest, db: AsyncSession = Depends(get_db)):
    """
    Ingest weekly data from file paths and run the Prime Cost pipeline.
    For browser-based file uploads use POST /upload instead.
    """
    raw_sales = await asyncio.to_thread(_load_csv, request.sales_path)
    raw_labor = await asyncio.to_thread(_load_csv, request.labor_path)
    raw_purchases = await asyncio.to_thread(_load_csv, request.purchases_path)

    return await _run_pipeline(raw_sales, raw_labor, raw_purchases, request.week_ending, db)


async def _run_pipeline(
    raw_sales: pd.DataFrame,
    raw_labor: pd.DataFrame,
    raw_purchases: pd.DataFrame,
    week_ending: date,
    db: AsyncSession,
) -> NuggetResponse:
    """
    Shared pipeline: normalize → resolve (once) → crunch → persist.
    Called by both /ingest and /upload.
    """
    clean = await asyncio.to_thread(build_clean_data, raw_sales, raw_labor, raw_purchases)

    mapping_dict = await load_mapping_dict(db)
    venue_lookup = await load_venue_lookup(db)

    # --- Entity Resolution: happens exactly once ---
    sales_resolved = resolve_dataframe(clean.sales, "toast", mapping_dict)
    labor_resolved = resolve_dataframe(clean.labor, "7shifts", mapping_dict)
    labor_roles_resolved = resolve_dataframe(clean.labor_roles, "7shifts", mapping_dict)
    purchases_resolved = resolve_dataframe(clean.purchases, "marketman", mapping_dict)

    # --- Crunch (pure math, pre-resolved DFs) ---
    nuggets: list[NuggetJSON] = await asyncio.to_thread(
        crunch_weekly_prime,
        sales_resolved,
        labor_resolved,
        purchases_resolved,
        venue_lookup,
        week_ending,
    )

    # --- Build drilldowns ---
    labor_drilldowns = []
    food_drilldowns = []

    for nugget in nuggets:
        labor_dd = await asyncio.to_thread(
            build_labor_drilldown,
            labor_roles_resolved,
            labor_resolved,
            nugget.venue_id,
            nugget.venue_name,
            week_ending,
        )
        labor_drilldowns.append(labor_dd)

        food_dd = await asyncio.to_thread(
            build_food_drilldown,
            purchases_resolved,
            nugget.venue_id,
            nugget.venue_name,
            week_ending,
            nugget.net_sales,
            nugget.food.target_pct / 100,
        )
        food_drilldowns.append(food_dd)

    # --- Persist (upsert via delete+insert) ---
    for nugget in nuggets:
        venue_uuid = uuid.UUID(nugget.venue_id)
        await db.execute(
            delete(WeeklyReport).where(
                and_(WeeklyReport.venue_id == venue_uuid, WeeklyReport.week_ending == week_ending)
            )
        )
        db.add(WeeklyReport(
            venue_id=venue_uuid,
            week_ending=week_ending,
            nugget_payload=nugget.model_dump(mode="json"),
        ))

    for dd in labor_drilldowns:
        venue_uuid = uuid.UUID(dd.venue_id)
        await db.execute(
            delete(LaborDrilldown).where(
                and_(LaborDrilldown.venue_id == venue_uuid, LaborDrilldown.week_ending == week_ending)
            )
        )
        db.add(LaborDrilldown(
            venue_id=venue_uuid,
            week_ending=week_ending,
            drilldown_payload=dd.model_dump(mode="json"),
        ))

    for dd in food_drilldowns:
        venue_uuid = uuid.UUID(dd.venue_id)
        await db.execute(
            delete(FoodDrilldown).where(
                and_(FoodDrilldown.venue_id == venue_uuid, FoodDrilldown.week_ending == week_ending)
            )
        )
        db.add(FoodDrilldown(
            venue_id=venue_uuid,
            week_ending=week_ending,
            drilldown_payload=dd.model_dump(mode="json"),
        ))

    return NuggetResponse(count=len(nuggets), week_ending=week_ending, nuggets=nuggets)
