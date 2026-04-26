"""
PrimeOps Agentic OS — Data Adapter Layer

Bridges the gap between raw real-world CSVs and the Cruncher's expected format.
Each source system has its own quirks — the adapter normalizes them all.

Transformation Pipeline:
  Raw CSV → adapt_*() → CleanData → resolver → cruncher → Nugget JSON

Design Rule: The Cruncher stays pure. The Adapter handles the mess.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Role → Type Mapping (BOH vs FOH)
# ---------------------------------------------------------------------------
ROLE_COLUMN_MAP: dict[str, tuple[str, str]] = {
    # column_name → (display_role, role_type)
    "server_hours": ("Server", "FOH"),
    "bartender_hours": ("Bartender", "FOH"),
    "host_hours": ("Host", "FOH"),
    "line_cook_hours": ("Line Cook", "BOH"),
    "prep_cook_hours": ("Prep Cook", "BOH"),
    "dishwasher_hours": ("Dishwasher", "BOH"),
    "mgmt_hours": ("Management", "MGT"),
}


# ---------------------------------------------------------------------------
# CleanData — The standardized container the Cruncher consumes
# ---------------------------------------------------------------------------
@dataclass
class CleanData:
    """
    Normalized data container produced by the adapter.
    All column names are standardized. Ready for entity resolution + crunching.
    """

    sales: pd.DataFrame
    """Columns: venue_ext_id, date, net_sales"""

    labor: pd.DataFrame
    """Columns: venue_ext_id, week_ending, actual_labor_cost,
    scheduled_hours, actual_hours, overtime_hours"""

    labor_roles: pd.DataFrame
    """For drilldown only. Columns: venue_ext_id, week_ending,
    role, role_type (BOH/FOH/MGT), hours"""

    purchases: pd.DataFrame
    """Columns: venue_ext_id, date, vendor, invoice_total, category"""


# ---------------------------------------------------------------------------
# Sales Adapter (POS / Toast)
# ---------------------------------------------------------------------------
def adapt_sales(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize POS daily sales data.

    Input columns (from raw CSV):
        date, venue, net_sales (+ any extras)

    Output columns:
        venue_ext_id, date, net_sales
    """
    df = df.copy()

    # Rename venue → venue_ext_id (the resolver's expected key)
    if "venue" in df.columns and "venue_ext_id" not in df.columns:
        df = df.rename(columns={"venue": "venue_ext_id"})

    # Ensure date is parsed
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])

    # Strip whitespace from venue names
    df["venue_ext_id"] = df["venue_ext_id"].astype(str).str.strip()

    # Ensure net_sales is numeric
    df["net_sales"] = pd.to_numeric(df["net_sales"], errors="coerce").fillna(0.0)

    # Keep only the columns we need
    required = ["venue_ext_id", "date", "net_sales"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Sales CSV missing required column: '{col}'")

    return df[required].copy()


# ---------------------------------------------------------------------------
# Labor Adapter (7shifts / Weekly Summary)
# ---------------------------------------------------------------------------
def adapt_labor(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Normalize weekly labor summary data.

    KEY RULE: Use 'actual_labor_cost' directly as truth. Do NOT back-calculate.
    Wide-format role columns are ONLY used for drilldown/BOH-FOH analysis.

    Input columns (from raw CSV):
        week_ending, venue, projected_sales, actual_sales,
        scheduled_hours, actual_hours, actual_labor_cost,
        server_hours, bartender_hours, host_hours,
        line_cook_hours, prep_cook_hours, dishwasher_hours,
        mgmt_hours, overtime_hours

    Returns:
        (labor_summary, labor_roles) tuple:
        - labor_summary: venue_ext_id, week_ending, actual_labor_cost,
                         scheduled_hours, actual_hours, overtime_hours
        - labor_roles: venue_ext_id, week_ending, role, role_type, hours
    """
    df = df.copy()

    # Rename venue → venue_ext_id
    if "venue" in df.columns and "venue_ext_id" not in df.columns:
        df = df.rename(columns={"venue": "venue_ext_id"})

    df["venue_ext_id"] = df["venue_ext_id"].astype(str).str.strip()

    # Parse week_ending date
    if "week_ending" in df.columns:
        df["week_ending"] = pd.to_datetime(df["week_ending"])

    # Ensure numeric columns
    numeric_cols = [
        "actual_labor_cost", "scheduled_hours", "actual_hours", "overtime_hours",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # --- Build labor_summary (what the cruncher uses for cost) ---
    summary_cols = [
        "venue_ext_id", "week_ending", "actual_labor_cost",
        "scheduled_hours", "actual_hours", "overtime_hours",
    ]
    
    required = ["venue_ext_id", "week_ending", "actual_labor_cost"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Labor CSV missing required column: '{col}'")
            
    labor_summary = df[[c for c in summary_cols if c in df.columns]].copy()

    # --- Build labor_roles (what the drilldown uses for role analysis) ---
    role_columns = [col for col in ROLE_COLUMN_MAP.keys() if col in df.columns]

    if role_columns:
        # Melt wide columns into long format
        id_vars = ["venue_ext_id", "week_ending"]
        roles_long = df.melt(
            id_vars=[c for c in id_vars if c in df.columns],
            value_vars=role_columns,
            var_name="role_column",
            value_name="hours",
        )

        # Map column names to display names and BOH/FOH type
        roles_long["role"] = roles_long["role_column"].map(
            lambda c: ROLE_COLUMN_MAP[c][0]
        )
        roles_long["role_type"] = roles_long["role_column"].map(
            lambda c: ROLE_COLUMN_MAP[c][1]
        )
        roles_long["hours"] = pd.to_numeric(roles_long["hours"], errors="coerce").fillna(0.0)

        labor_roles = roles_long[
            [c for c in ["venue_ext_id", "week_ending", "role", "role_type", "hours"]
             if c in roles_long.columns]
        ].copy()
    else:
        # No role columns found — return empty DataFrame with correct schema
        labor_roles = pd.DataFrame(
            columns=["venue_ext_id", "week_ending", "role", "role_type", "hours"]
        )

    return labor_summary, labor_roles


# ---------------------------------------------------------------------------
# Purchases Adapter (MarketMan)
# ---------------------------------------------------------------------------
def adapt_purchases(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize purchase/invoice data.

    Input columns (from raw CSV):
        venue_id, date, vendor, amount, category (+ any extras)

    Output columns:
        venue_ext_id, date, vendor, invoice_total, category
    """
    df = df.copy()

    # Rename columns to match cruncher expectations
    rename_map = {}
    if "venue_id" in df.columns and "venue_ext_id" not in df.columns:
        rename_map["venue_id"] = "venue_ext_id"
    if "amount" in df.columns and "invoice_total" not in df.columns:
        rename_map["amount"] = "invoice_total"

    if rename_map:
        df = df.rename(columns=rename_map)

    df["venue_ext_id"] = df["venue_ext_id"].astype(str).str.strip()

    # Parse dates
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])

    # Ensure numeric
    df["invoice_total"] = pd.to_numeric(df["invoice_total"], errors="coerce").fillna(0.0)

    # Keep required columns
    required = ["venue_ext_id", "date", "invoice_total"]
    optional = ["vendor", "category"]
    keep = required + [c for c in optional if c in df.columns]

    for col in required:
        if col not in df.columns:
            raise ValueError(f"Purchases CSV missing required column: '{col}'")

    return df[keep].copy()


# ---------------------------------------------------------------------------
# Full Pipeline: Raw CSVs → CleanData
# ---------------------------------------------------------------------------
def build_clean_data(
    raw_sales: pd.DataFrame,
    raw_labor: pd.DataFrame,
    raw_purchases: pd.DataFrame,
) -> CleanData:
    """
    Run the full adapter pipeline on raw CSVs.

    Args:
        raw_sales: Raw POS daily sales DataFrame.
        raw_labor: Raw weekly labor summary DataFrame.
        raw_purchases: Raw purchase/invoice DataFrame.

    Returns:
        CleanData with all DataFrames normalized and ready for the resolver.
    """
    sales = adapt_sales(raw_sales)
    labor_summary, labor_roles = adapt_labor(raw_labor)
    purchases = adapt_purchases(raw_purchases)

    return CleanData(
        sales=sales,
        labor=labor_summary,
        labor_roles=labor_roles,
        purchases=purchases,
    )
