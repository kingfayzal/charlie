"""
PrimeOps Agentic OS — POST /upload
Browser-facing endpoint. The data is now hardcoded into the codebase under
``data/``; this route ignores the uploaded files and runs the pipeline on
the bundled CSVs (Central Ave / Riverside / Downtown demo dataset).
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routes.ingest import _run_pipeline
from app.schemas import NuggetResponse


router = APIRouter(tags=["Ingest"])

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_SALES_PATH = _DATA_DIR / "pos_daily_sales.csv"
_LABOR_PATH = _DATA_DIR / "labor_summary.csv"
_PURCHASES_PATH = _DATA_DIR / "purchases.csv"


def _filter_week(df: pd.DataFrame, date_col: str, week_start: date, week_end: date) -> pd.DataFrame:
    if date_col not in df.columns:
        return df
    parsed = pd.to_datetime(df[date_col], errors="coerce")
    mask = (parsed.dt.date >= week_start) & (parsed.dt.date <= week_end)
    return df[mask].copy()


@router.post("/upload", response_model=NuggetResponse)
async def upload_and_ingest(
    sales_file: UploadFile = File(None, description="Ignored — bundled CSV is used"),
    labor_file: UploadFile = File(None, description="Ignored — bundled CSV is used"),
    purchases_file: UploadFile = File(None, description="Ignored — bundled CSV is used"),
    week_ending: date = Form(..., description="The Sunday that ends the reporting week"),
    db: AsyncSession = Depends(get_db),
):
    """Run the Prime Cost engine on the hardcoded bundled dataset."""
    try:
        raw_sales = pd.read_csv(_SALES_PATH)
        raw_labor = pd.read_csv(_LABOR_PATH)
        raw_purchases = pd.read_csv(_PURCHASES_PATH)

        week_start = week_ending - timedelta(days=6)
        raw_sales = _filter_week(raw_sales, "date", week_start, week_ending)
        raw_purchases = _filter_week(raw_purchases, "invoice_date", week_start, week_ending)
        if "week_ending" in raw_labor.columns:
            raw_labor = raw_labor[
                pd.to_datetime(raw_labor["week_ending"], errors="coerce").dt.date == week_ending
            ].copy()

        return await _run_pipeline(raw_sales, raw_labor, raw_purchases, week_ending, db)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
