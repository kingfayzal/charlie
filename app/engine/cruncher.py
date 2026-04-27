"""
PrimeOps Agentic OS — Data Engine (Cruncher) v3

The deterministic core. All math lives here. No LLM calls. No resolution.

IMPORTANT: All DataFrames passed in must already have 'universal_venue_id'
resolved by the caller (app/routes/ingest.py or app/routes/upload.py).
Resolution was moved out of the cruncher so it happens exactly once per request.

Pipeline: Raw CSVs → adapter → resolver (caller) → cruncher → Nugget JSON

Business Rules (from CONTEXT.md):
  - Net Sales is the denominator for ALL percentages.
  - Prime Cost = (Actual Labor Cost + Actual Food Purchases) / Net Sales.
  - Labor Actuals use 'actual_labor_cost' directly — never back-calculate from hours.
  - Food Cost uses Purchases-to-Sales method (total invoices / net sales).
  - If data is incomplete for a venue → DataReadinessError (never partial calcs).
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from app.schemas import (
    CategoryDetail,
    DataQuality,
    FoodDrilldownResponse,
    LaborDrilldownResponse,
    MetricDetail,
    NuggetJSON,
    RoleDetail,
    VendorDetail,
)
from app.errors import DataReadinessError


# ---------------------------------------------------------------------------
# Data Readiness Check
# ---------------------------------------------------------------------------
def _check_data_readiness(
    sales_df: pd.DataFrame,
    labor_df: pd.DataFrame,
    purchases_df: pd.DataFrame,
    venue_lookup: dict[str, dict],
) -> None:
    """
    Verify all three data sources exist for every venue present in sales.
    All DataFrames must already have 'universal_venue_id' column.
    Raises DataReadinessError on the first incomplete venue found.
    """
    sales_venues = set(sales_df["universal_venue_id"].unique())
    labor_venues = set(labor_df["universal_venue_id"].unique())
    purchases_venues = set(purchases_df["universal_venue_id"].unique())

    for venue_id in sales_venues:
        venue_info = venue_lookup.get(venue_id, {"name": f"Unknown ({venue_id})"})
        venue_name = venue_info["name"]

        if venue_id not in labor_venues:
            raise DataReadinessError(
                venue_name=venue_name,
                detail="Labor data is completely missing for this period.",
                missing_sources=["labor"],
            )

        if venue_id not in purchases_venues:
            raise DataReadinessError(
                venue_name=venue_name,
                detail="Purchase/invoice data is completely missing for this period.",
                missing_sources=["purchases"],
            )

        # Day-level granularity check intentionally omitted: invoice cadence
        # (vendor delivery days) does not need to mirror sales days. The
        # Purchases-to-Sales method only requires the weekly invoice total.


# ---------------------------------------------------------------------------
# Core Calculation Engine
# ---------------------------------------------------------------------------
def crunch_weekly_prime(
    sales_df: pd.DataFrame,
    labor_df: pd.DataFrame,
    purchases_df: pd.DataFrame,
    venue_lookup: dict[str, dict],
    week_ending: date,
) -> list[NuggetJSON]:
    """
    Calculate weekly Prime Cost metrics per venue.

    Args:
        sales_df: Resolved daily sales (must have universal_venue_id).
        labor_df: Resolved weekly labor summary (must have universal_venue_id).
        purchases_df: Resolved daily purchases (must have universal_venue_id).
        venue_lookup: {venue_id → {name, target_prime_pct, ...}}
        week_ending: The Saturday ending the reporting week.

    Returns:
        List of NuggetJSON objects (one per venue).
    """
    _check_data_readiness(sales_df, labor_df, purchases_df, venue_lookup)

    nuggets: list[NuggetJSON] = []

    for venue_id in sales_df["universal_venue_id"].unique():
        venue_info = venue_lookup.get(venue_id)
        if not venue_info:
            continue

        v_sales = sales_df[sales_df["universal_venue_id"] == venue_id]
        v_labor = labor_df[labor_df["universal_venue_id"] == venue_id]
        v_purchases = purchases_df[purchases_df["universal_venue_id"] == venue_id]

        net_sales = float(v_sales["net_sales"].sum())
        if net_sales <= 0:
            continue

        # Labor — use actual_labor_cost directly, never back-calculate
        actual_labor_cost = float(v_labor["actual_labor_cost"].sum())
        actual_labor_pct = actual_labor_cost / net_sales

        # Food — Purchases-to-Sales method
        actual_food_cost = float(v_purchases["invoice_total"].sum())
        actual_food_pct = actual_food_cost / net_sales

        # Prime
        actual_prime_pct = actual_labor_pct + actual_food_pct

        target_labor = venue_info["target_labor_pct"]
        target_food = venue_info["target_food_pct"]
        target_prime = venue_info["target_prime_pct"]

        labor_variance = actual_labor_pct - target_labor
        food_variance = actual_food_pct - target_food
        prime_variance = actual_prime_pct - target_prime

        if abs(labor_variance) >= abs(food_variance):
            primary_driver = "labor"
            overtime_hours = (
                float(v_labor["overtime_hours"].sum())
                if "overtime_hours" in v_labor.columns
                else 0.0
            )
            driver_detail = _build_labor_driver_detail(
                labor_variance, food_variance, overtime_hours, actual_labor_cost
            )
        else:
            primary_driver = "food"
            driver_detail = _build_food_driver_detail(food_variance, labor_variance, v_purchases)

        nuggets.append(NuggetJSON(
            venue_id=venue_id,
            venue_name=venue_info["name"],
            week_ending=week_ending,
            net_sales=round(net_sales, 2),
            labor=MetricDetail(
                actual_pct=round(actual_labor_pct * 100, 1),
                target_pct=round(target_labor * 100, 1),
                variance_pct=round(labor_variance * 100, 1),
                actual_cost=round(actual_labor_cost, 2),
            ),
            food=MetricDetail(
                actual_pct=round(actual_food_pct * 100, 1),
                target_pct=round(target_food * 100, 1),
                variance_pct=round(food_variance * 100, 1),
                actual_cost=round(actual_food_cost, 2),
            ),
            prime=MetricDetail(
                actual_pct=round(actual_prime_pct * 100, 1),
                target_pct=round(target_prime * 100, 1),
                variance_pct=round(prime_variance * 100, 1),
                actual_cost=round(actual_labor_cost + actual_food_cost, 2),
            ),
            primary_driver=primary_driver,
            driver_detail=driver_detail,
            data_quality=DataQuality(status="complete", missing_sources=[], missing_days=[]),
        ))

    return nuggets


# ---------------------------------------------------------------------------
# Driver Detail Builders
# ---------------------------------------------------------------------------
def _build_labor_driver_detail(
    labor_var: float,
    food_var: float,
    overtime_hours: float,
    actual_labor_cost: float,
) -> str:
    direction = "over" if labor_var > 0 else "under"
    parts = [
        f"Labor is {abs(labor_var * 100):.1f}pp {direction} target "
        f"vs Food at {abs(food_var * 100):.1f}pp."
    ]
    if overtime_hours > 0:
        parts.append(
            f"{overtime_hours:.1f} overtime hours recorded "
            f"(total labor cost: ${actual_labor_cost:,.0f})."
        )
    return " ".join(parts)


def _build_food_driver_detail(
    food_var: float,
    labor_var: float,
    purchases_df: pd.DataFrame,
) -> str:
    direction = "over" if food_var > 0 else "under"
    parts = [
        f"Food is {abs(food_var * 100):.1f}pp {direction} target "
        f"vs Labor at {abs(labor_var * 100):.1f}pp."
    ]
    if "category" in purchases_df.columns:
        cost_by_cat = (
            purchases_df.groupby("category")["invoice_total"]
            .sum()
            .sort_values(ascending=False)
        )
        if len(cost_by_cat) > 0:
            top_cat = cost_by_cat.index[0]
            top_val = cost_by_cat.iloc[0]
            parts.append(f"Top spend category: {top_cat} (${top_val:,.0f}).")
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Labor Drilldown
# ---------------------------------------------------------------------------
def build_labor_drilldown(
    labor_roles_df: pd.DataFrame,
    labor_summary_df: pd.DataFrame,
    venue_id: str,
    venue_name: str,
    week_ending: date,
) -> LaborDrilldownResponse:
    """
    Build role-level labor detail for a single venue.
    Both DataFrames must already have 'universal_venue_id' resolved.
    """
    v_roles = labor_roles_df[labor_roles_df["universal_venue_id"] == venue_id].copy()
    v_summary = labor_summary_df[labor_summary_df["universal_venue_id"] == venue_id]

    total_labor_cost = float(v_summary["actual_labor_cost"].sum()) if len(v_summary) > 0 else 0.0
    total_overtime_hours = (
        float(v_summary["overtime_hours"].sum())
        if "overtime_hours" in v_summary.columns
        else 0.0
    )

    roles: list[RoleDetail] = []

    if len(v_roles) > 0:
        role_groups = v_roles.groupby(["role", "role_type"]).agg(
            hours=("hours", "sum"),
        ).reset_index()

        total_hours = float(role_groups["hours"].sum())

        for _, row in role_groups.iterrows():
            role_hours = float(row["hours"])
            hours_pct = role_hours / total_hours if total_hours > 0 else 0.0
            estimated_cost = total_labor_cost * hours_pct
            estimated_ot_hours = total_overtime_hours * hours_pct

            roles.append(RoleDetail(
                role=row["role"],
                role_type=row["role_type"],
                headcount=0,
                hours_scheduled=0.0,
                hours_worked=round(role_hours, 1),
                hours_variance=0.0,
                overtime_hours=round(estimated_ot_hours, 1),
                overtime_cost=0.0,
                total_cost=round(estimated_cost, 2),
            ))

    boh_roles = [r for r in roles if r.role_type == "BOH"]
    foh_roles = [r for r in roles if r.role_type == "FOH"]

    boh_summary = {
        "total_hours": round(sum(r.hours_worked for r in boh_roles), 1),
        "total_overtime": round(sum(r.overtime_hours for r in boh_roles), 1),
        "total_cost": round(sum(r.total_cost for r in boh_roles), 2),
        "headcount": sum(r.headcount for r in boh_roles),
    }
    foh_summary = {
        "total_hours": round(sum(r.hours_worked for r in foh_roles), 1),
        "total_overtime": round(sum(r.overtime_hours for r in foh_roles), 1),
        "total_cost": round(sum(r.total_cost for r in foh_roles), 2),
        "headcount": sum(r.headcount for r in foh_roles),
    }

    total_ot_cost = 0.0
    ot_pct = 0.0
    if total_overtime_hours > 0 and total_labor_cost > 0:
        actual = (
            float(v_summary["actual_hours"].sum())
            if "actual_hours" in v_summary.columns
            else 0.0
        )
        if actual > 0:
            ot_pct_of_hours = total_overtime_hours / actual
            total_ot_cost = total_labor_cost * ot_pct_of_hours
            ot_pct = total_ot_cost / total_labor_cost * 100

    return LaborDrilldownResponse(
        venue_id=venue_id,
        venue_name=venue_name,
        week_ending=week_ending,
        total_labor_cost=round(total_labor_cost, 2),
        total_overtime_cost=round(total_ot_cost, 2),
        overtime_pct_of_labor=round(ot_pct, 1),
        boh_summary=boh_summary,
        foh_summary=foh_summary,
        roles=roles,
    )


# ---------------------------------------------------------------------------
# Food Cost Drilldown
# ---------------------------------------------------------------------------
def build_food_drilldown(
    purchases_df: pd.DataFrame,
    venue_id: str,
    venue_name: str,
    week_ending: date,
    net_sales: float,
    target_food_pct: float,
) -> FoodDrilldownResponse:
    """
    Build category and vendor breakdown for food cost for a single venue.
    purchases_df must already have 'universal_venue_id' resolved.
    """
    v_purchases = purchases_df[purchases_df["universal_venue_id"] == venue_id]

    total_food_cost = float(v_purchases["invoice_total"].sum()) if len(v_purchases) > 0 else 0.0
    food_pct = (total_food_cost / net_sales * 100) if net_sales > 0 else 0.0
    variance_pct = food_pct - (target_food_pct * 100)

    # Category breakdown
    categories: list[CategoryDetail] = []
    if "category" in v_purchases.columns and len(v_purchases) > 0:
        cat_totals = (
            v_purchases.groupby("category")["invoice_total"]
            .sum()
            .sort_values(ascending=False)
        )
        for cat, cost in cat_totals.items():
            pct = (cost / total_food_cost * 100) if total_food_cost > 0 else 0.0
            categories.append(CategoryDetail(
                category=str(cat),
                total_cost=round(float(cost), 2),
                pct_of_food_spend=round(float(pct), 1),
            ))

    # Vendor breakdown
    vendors: list[VendorDetail] = []
    if "vendor" in v_purchases.columns and len(v_purchases) > 0:
        vendor_agg = (
            v_purchases.groupby("vendor")
            .agg(total_cost=("invoice_total", "sum"), invoice_count=("invoice_total", "count"))
            .sort_values("total_cost", ascending=False)
            .reset_index()
        )
        for _, row in vendor_agg.iterrows():
            cost = float(row["total_cost"])
            pct = (cost / total_food_cost * 100) if total_food_cost > 0 else 0.0
            vendors.append(VendorDetail(
                vendor=str(row["vendor"]),
                total_cost=round(cost, 2),
                invoice_count=int(row["invoice_count"]),
                pct_of_food_spend=round(pct, 1),
            ))

    return FoodDrilldownResponse(
        venue_id=venue_id,
        venue_name=venue_name,
        week_ending=week_ending,
        total_food_cost=round(total_food_cost, 2),
        food_pct=round(food_pct, 1),
        target_food_pct=round(target_food_pct * 100, 1),
        variance_pct=round(variance_pct, 1),
        categories=categories,
        vendors=vendors,
    )
