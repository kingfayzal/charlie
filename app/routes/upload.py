"""
PrimeOps Agentic OS — POST /upload
Accepts multipart CSV file uploads directly from the browser, then runs
the same ingest pipeline as POST /ingest.
"""

from __future__ import annotations

import io
from datetime import date

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.routes.ingest import _run_pipeline
from app.schemas import NuggetResponse


router = APIRouter(tags=["Ingest"])


@router.post("/upload", response_model=NuggetResponse)
async def upload_and_ingest(
    sales_file: UploadFile = File(..., description="POS daily sales CSV (Toast)"),
    labor_file: UploadFile = File(..., description="Weekly labor summary CSV (7shifts)"),
    purchases_file: UploadFile = File(..., description="Purchase invoices CSV (MarketMan)"),
    week_ending: date = Form(..., description="The Saturday that ends the reporting week"),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload three CSV files and run the Prime Cost engine.

    This is the browser-facing equivalent of POST /ingest (which takes file paths).
    Accepts multipart/form-data so the frontend can send files directly.
    """
    raw_sales = pd.read_csv(io.BytesIO(await sales_file.read()))
    raw_labor = pd.read_csv(io.BytesIO(await labor_file.read()))
    raw_purchases = pd.read_csv(io.BytesIO(await purchases_file.read()))

    return await _run_pipeline(raw_sales, raw_labor, raw_purchases, week_ending, db)
