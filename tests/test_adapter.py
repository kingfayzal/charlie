"""
PrimeOps Agentic OS — Adapter Unit Tests
Tests the data transformation layer that bridges raw CSVs to the Cruncher.
"""

import pandas as pd
import pytest

from app.engine.adapter import (
    adapt_sales,
    adapt_labor,
    adapt_purchases,
    build_clean_data,
    ROLE_COLUMN_MAP,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _raw_sales_df() -> pd.DataFrame:
    return pd.DataFrame({
        "date": ["2026-03-01", "2026-03-02"],
        "venue": ["Central Ave", "Central Ave"],
        "net_sales": [5486.43, 5486.43],
        "gross_sales": [5948.00, 5948.00],
    })


def _raw_labor_df() -> pd.DataFrame:
    return pd.DataFrame({
        "week_ending": ["2026-03-08"],
        "venue": ["Central Ave"],
        "projected_sales": [38500],
        "actual_sales": [38405],
        "scheduled_hours": [545],
        "actual_hours": [546],
        "actual_labor_cost": [12289],
        "server_hours": [200],
        "bartender_hours": [45],
        "host_hours": [35],
        "line_cook_hours": [125],
        "prep_cook_hours": [48],
        "dishwasher_hours": [43],
        "mgmt_hours": [50],
        "overtime_hours": [1.5],
    })


def _raw_purchases_df() -> pd.DataFrame:
    return pd.DataFrame({
        "venue_id": ["heathfield", "heathfield"],
        "date": ["2026-03-01", "2026-03-02"],
        "vendor": ["Sysco", "US Foods"],
        "amount": [1245.50, 876.25],
        "category": ["Protein", "Produce"],
    })


# ---------------------------------------------------------------------------
# Sales Adapter Tests
# ---------------------------------------------------------------------------
class TestAdaptSales:

    def test_renames_venue_to_venue_ext_id(self):
        result = adapt_sales(_raw_sales_df())
        assert "venue_ext_id" in result.columns
        assert "venue" not in result.columns

    def test_keeps_only_required_columns(self):
        result = adapt_sales(_raw_sales_df())
        assert list(result.columns) == ["venue_ext_id", "date", "net_sales"]

    def test_parses_dates(self):
        result = adapt_sales(_raw_sales_df())
        assert pd.api.types.is_datetime64_any_dtype(result["date"])

    def test_strips_whitespace(self):
        df = _raw_sales_df()
        df["venue"] = "  Central Ave  "
        result = adapt_sales(df)
        assert result["venue_ext_id"].iloc[0] == "Central Ave"


# ---------------------------------------------------------------------------
# Labor Adapter Tests
# ---------------------------------------------------------------------------
class TestAdaptLabor:

    def test_returns_tuple(self):
        result = adapt_labor(_raw_labor_df())
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_summary_has_actual_labor_cost(self):
        summary, _ = adapt_labor(_raw_labor_df())
        assert "actual_labor_cost" in summary.columns
        assert summary["actual_labor_cost"].iloc[0] == 12289

    def test_summary_uses_venue_ext_id(self):
        summary, _ = adapt_labor(_raw_labor_df())
        assert "venue_ext_id" in summary.columns
        assert summary["venue_ext_id"].iloc[0] == "Central Ave"

    def test_roles_pivoted_to_long_format(self):
        _, roles = adapt_labor(_raw_labor_df())
        assert "role" in roles.columns
        assert "role_type" in roles.columns
        assert "hours" in roles.columns
        # Should have 7 roles: server, bartender, host, line_cook, prep_cook, dishwasher, mgmt
        assert len(roles) == 7

    def test_roles_have_correct_boh_foh(self):
        _, roles = adapt_labor(_raw_labor_df())
        boh = roles[roles["role_type"] == "BOH"]
        foh = roles[roles["role_type"] == "FOH"]
        assert len(boh) == 3  # Line Cook, Prep Cook, Dishwasher
        assert len(foh) == 3  # Server, Bartender, Host

    def test_server_hours_correct(self):
        _, roles = adapt_labor(_raw_labor_df())
        server = roles[roles["role"] == "Server"]
        assert float(server["hours"].iloc[0]) == 200.0


# ---------------------------------------------------------------------------
# Purchases Adapter Tests
# ---------------------------------------------------------------------------
class TestAdaptPurchases:

    def test_renames_amount_to_invoice_total(self):
        result = adapt_purchases(_raw_purchases_df())
        assert "invoice_total" in result.columns
        assert "amount" not in result.columns

    def test_renames_venue_id_to_venue_ext_id(self):
        result = adapt_purchases(_raw_purchases_df())
        assert "venue_ext_id" in result.columns
        assert "venue_id" not in result.columns

    def test_invoice_total_values(self):
        result = adapt_purchases(_raw_purchases_df())
        assert result["invoice_total"].iloc[0] == 1245.50


# ---------------------------------------------------------------------------
# Full Pipeline Tests
# ---------------------------------------------------------------------------
class TestBuildCleanData:

    def test_returns_clean_data_object(self):
        clean = build_clean_data(
            _raw_sales_df(), _raw_labor_df(), _raw_purchases_df()
        )
        assert hasattr(clean, "sales")
        assert hasattr(clean, "labor")
        assert hasattr(clean, "labor_roles")
        assert hasattr(clean, "purchases")

    def test_all_dataframes_have_venue_ext_id(self):
        clean = build_clean_data(
            _raw_sales_df(), _raw_labor_df(), _raw_purchases_df()
        )
        assert "venue_ext_id" in clean.sales.columns
        assert "venue_ext_id" in clean.labor.columns
        assert "venue_ext_id" in clean.purchases.columns
