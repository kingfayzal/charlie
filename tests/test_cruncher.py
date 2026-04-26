"""
PrimeOps Agentic OS — Cruncher v3 Unit Tests

Tests the refactored Data Engine (v3) where resolution happens before crunch.
Callers must resolve DataFrames first; the cruncher receives pre-resolved DFs.
"""

from datetime import date

import pandas as pd
import pytest

from app.engine.adapter import CleanData
from app.engine.cruncher import build_food_drilldown, build_labor_drilldown, crunch_weekly_prime
from app.engine.resolver import resolve_dataframe
from app.errors import DataReadinessError


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VENUE_ID = "aaaa-bbbb-cccc-dddd"
VENUE_NAME = "Central Ave"
WEEK_ENDING = date(2026, 3, 8)

MAPPING_DICT = {
    ("Central Ave", "toast"): VENUE_ID,
    ("Central Ave", "7shifts"): VENUE_ID,
    ("heathfield", "marketman"): VENUE_ID,
}

VENUE_LOOKUP = {
    VENUE_ID: {
        "name": VENUE_NAME,
        "target_prime_pct": 0.58,
        "target_labor_pct": 0.30,
        "target_food_pct": 0.28,
    }
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_clean_data(include_purchases: bool = True) -> CleanData:
    days = pd.date_range("2026-03-02", periods=7, freq="D")

    sales = pd.DataFrame({
        "venue_ext_id": ["Central Ave"] * 7,
        "date": days,
        "net_sales": [5486.43] * 7,
    })

    labor = pd.DataFrame({
        "venue_ext_id": ["Central Ave"],
        "week_ending": [pd.Timestamp("2026-03-08")],
        "actual_labor_cost": [12289.0],
        "scheduled_hours": [545.0],
        "actual_hours": [546.0],
        "overtime_hours": [1.5],
    })

    labor_roles = pd.DataFrame({
        "venue_ext_id": ["Central Ave"] * 7,
        "week_ending": [pd.Timestamp("2026-03-08")] * 7,
        "role": ["Server", "Bartender", "Host", "Line Cook", "Prep Cook", "Dishwasher", "Management"],
        "role_type": ["FOH", "FOH", "FOH", "BOH", "BOH", "BOH", "MGT"],
        "hours": [200, 45, 35, 125, 48, 43, 50],
    })

    if include_purchases:
        purchases = pd.DataFrame({
            "venue_ext_id": ["heathfield"] * 7,
            "date": days,
            "vendor": ["Sysco"] * 7,
            "invoice_total": [1500.0] * 7,
            "category": ["Protein"] * 7,
        })
    else:
        purchases = pd.DataFrame(
            columns=["venue_ext_id", "date", "vendor", "invoice_total", "category"]
        )

    return CleanData(sales=sales, labor=labor, labor_roles=labor_roles, purchases=purchases)


def _resolve(clean: CleanData):
    """Resolve a CleanData object and return pre-resolved DataFrames."""
    return (
        resolve_dataframe(clean.sales, "toast", MAPPING_DICT),
        resolve_dataframe(clean.labor, "7shifts", MAPPING_DICT),
        resolve_dataframe(clean.purchases, "marketman", MAPPING_DICT),
    )


# ---------------------------------------------------------------------------
# Tests: crunch_weekly_prime
# ---------------------------------------------------------------------------
class TestCrunchWeeklyPrime:

    def test_uses_actual_labor_cost_directly(self):
        clean = _make_clean_data()
        sales_df, labor_df, purchases_df = _resolve(clean)

        nuggets = crunch_weekly_prime(sales_df, labor_df, purchases_df, VENUE_LOOKUP, WEEK_ENDING)

        assert len(nuggets) == 1
        assert nuggets[0].labor.actual_cost == 12289.0

    def test_net_sales_correct(self):
        clean = _make_clean_data()
        sales_df, labor_df, purchases_df = _resolve(clean)

        nuggets = crunch_weekly_prime(sales_df, labor_df, purchases_df, VENUE_LOOKUP, WEEK_ENDING)

        assert nuggets[0].net_sales == 38405.01  # 7 × $5,486.43

    def test_food_cost_correct(self):
        clean = _make_clean_data()
        sales_df, labor_df, purchases_df = _resolve(clean)

        nuggets = crunch_weekly_prime(sales_df, labor_df, purchases_df, VENUE_LOOKUP, WEEK_ENDING)

        assert nuggets[0].food.actual_cost == 10500.0  # 7 × $1,500

    def test_prime_cost_is_labor_plus_food(self):
        clean = _make_clean_data()
        sales_df, labor_df, purchases_df = _resolve(clean)

        nuggets = crunch_weekly_prime(sales_df, labor_df, purchases_df, VENUE_LOOKUP, WEEK_ENDING)
        n = nuggets[0]

        assert n.prime.actual_cost == n.labor.actual_cost + n.food.actual_cost
        assert abs(n.prime.actual_pct - (n.labor.actual_pct + n.food.actual_pct)) < 0.2

    def test_primary_driver_identified(self):
        clean = _make_clean_data()
        sales_df, labor_df, purchases_df = _resolve(clean)

        nuggets = crunch_weekly_prime(sales_df, labor_df, purchases_df, VENUE_LOOKUP, WEEK_ENDING)
        n = nuggets[0]

        assert n.primary_driver in ("labor", "food")
        assert len(n.driver_detail) > 0

    def test_nugget_structure_complete(self):
        clean = _make_clean_data()
        sales_df, labor_df, purchases_df = _resolve(clean)

        nuggets = crunch_weekly_prime(sales_df, labor_df, purchases_df, VENUE_LOOKUP, WEEK_ENDING)
        n = nuggets[0]

        assert n.venue_id == VENUE_ID
        assert n.venue_name == VENUE_NAME
        assert n.week_ending == WEEK_ENDING
        assert n.data_quality.status == "complete"


# ---------------------------------------------------------------------------
# Tests: Data Readiness guard
# ---------------------------------------------------------------------------
class TestDataReadiness:

    def test_missing_purchases_raises_error(self):
        clean = _make_clean_data(include_purchases=False)
        sales_df, labor_df, purchases_df = _resolve(clean)

        with pytest.raises(DataReadinessError) as exc_info:
            crunch_weekly_prime(sales_df, labor_df, purchases_df, VENUE_LOOKUP, WEEK_ENDING)

        assert "purchases" in exc_info.value.missing_sources

    def test_missing_labor_raises_error(self):
        clean = _make_clean_data()
        clean.labor = pd.DataFrame(
            columns=["venue_ext_id", "week_ending", "actual_labor_cost",
                     "scheduled_hours", "actual_hours", "overtime_hours"]
        )
        sales_df, labor_df, purchases_df = _resolve(clean)

        with pytest.raises(DataReadinessError) as exc_info:
            crunch_weekly_prime(sales_df, labor_df, purchases_df, VENUE_LOOKUP, WEEK_ENDING)

        assert "labor" in exc_info.value.missing_sources


# ---------------------------------------------------------------------------
# Tests: Labor Drilldown
# ---------------------------------------------------------------------------
class TestLaborDrilldown:

    def test_boh_foh_split(self):
        clean = _make_clean_data()
        labor_roles_df = resolve_dataframe(clean.labor_roles, "7shifts", MAPPING_DICT)
        labor_df = resolve_dataframe(clean.labor, "7shifts", MAPPING_DICT)

        result = build_labor_drilldown(
            labor_roles_df=labor_roles_df,
            labor_summary_df=labor_df,
            venue_id=VENUE_ID,
            venue_name=VENUE_NAME,
            week_ending=WEEK_ENDING,
        )

        assert result.venue_id == VENUE_ID
        assert result.total_labor_cost == 12289.0
        assert result.boh_summary["total_hours"] == 216.0   # 125+48+43
        assert result.foh_summary["total_hours"] == 280.0   # 200+45+35


# ---------------------------------------------------------------------------
# Tests: Food Drilldown
# ---------------------------------------------------------------------------
class TestFoodDrilldown:

    def test_category_breakdown(self):
        clean = _make_clean_data()
        purchases_df = resolve_dataframe(clean.purchases, "marketman", MAPPING_DICT)

        result = build_food_drilldown(
            purchases_df=purchases_df,
            venue_id=VENUE_ID,
            venue_name=VENUE_NAME,
            week_ending=WEEK_ENDING,
            net_sales=38405.01,
            target_food_pct=0.28,
        )

        assert result.total_food_cost == 10500.0
        assert len(result.categories) == 1
        assert result.categories[0].category == "Protein"
        assert result.categories[0].pct_of_food_spend == 100.0

    def test_vendor_breakdown(self):
        clean = _make_clean_data()
        purchases_df = resolve_dataframe(clean.purchases, "marketman", MAPPING_DICT)

        result = build_food_drilldown(
            purchases_df=purchases_df,
            venue_id=VENUE_ID,
            venue_name=VENUE_NAME,
            week_ending=WEEK_ENDING,
            net_sales=38405.01,
            target_food_pct=0.28,
        )

        assert len(result.vendors) == 1
        assert result.vendors[0].vendor == "Sysco"
        assert result.vendors[0].invoice_count == 7
