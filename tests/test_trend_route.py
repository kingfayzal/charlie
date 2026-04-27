"""
Charlie -- Sentinel / Trend Tests

Tests for the TrendResponse schema and FORECAST: note prefix behavior.
No DB or HTTP server required -- pure schema validation and string logic.
"""

from datetime import date

import pytest

from app.schemas import MetricDetail, TrendResponse, WeeklySnapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _metric(actual_pct: float = 30.0, target_pct: float = 30.0) -> MetricDetail:
    return MetricDetail(
        actual_pct=actual_pct,
        target_pct=target_pct,
        variance_pct=round(actual_pct - target_pct, 1),
        actual_cost=10000.0,
    )


def _snapshot(week_ending: date, prime_pct: float = 62.0) -> WeeklySnapshot:
    return WeeklySnapshot(
        week_ending=week_ending,
        net_sales=40000.0,
        prime=_metric(prime_pct, 60.0),
        labor=_metric(34.0, 30.0),
        food=_metric(28.0, 28.0),
        primary_driver="labor",
    )


# ---------------------------------------------------------------------------
# WeeklySnapshot schema
# ---------------------------------------------------------------------------
class TestWeeklySnapshotSchema:

    def test_serializes_all_fields(self):
        snap = _snapshot(date(2026, 3, 8), prime_pct=62.5)
        data = snap.model_dump()
        assert data["week_ending"] == date(2026, 3, 8)
        assert data["net_sales"] == 40000.0
        assert data["prime"]["actual_pct"] == 62.5
        assert data["primary_driver"] == "labor"

    def test_variance_sign_convention(self):
        # Positive variance = over target (bad for cost metrics)
        snap = _snapshot(date(2026, 3, 8), prime_pct=63.0)
        assert snap.prime.variance_pct > 0  # over target

    def test_at_target_zero_variance(self):
        snap = WeeklySnapshot(
            week_ending=date(2026, 3, 8),
            net_sales=40000.0,
            prime=_metric(60.0, 60.0),
            labor=_metric(30.0, 30.0),
            food=_metric(28.0, 28.0),
            primary_driver="food",
        )
        assert snap.prime.variance_pct == 0.0


# ---------------------------------------------------------------------------
# TrendResponse schema -- ordering contract
# ---------------------------------------------------------------------------
class TestTrendResponseSchema:

    def test_oldest_first_ordering(self):
        snaps = [
            _snapshot(date(2026, 3, 1), prime_pct=61.0),
            _snapshot(date(2026, 3, 8), prime_pct=62.0),
            _snapshot(date(2026, 3, 15), prime_pct=63.0),
        ]
        tr = TrendResponse(venue_id="abc", venue_name="Riverside", weeks=3, snapshots=snaps)
        dates = [s.week_ending for s in tr.snapshots]
        assert dates == sorted(dates), "snapshots must be oldest to newest"

    def test_weeks_reflects_actual_count(self):
        snaps = [_snapshot(date(2026, 3, 1)), _snapshot(date(2026, 3, 8))]
        tr = TrendResponse(venue_id="abc", venue_name="Riverside", weeks=len(snaps), snapshots=snaps)
        assert tr.weeks == 2

    def test_empty_history_is_valid(self):
        tr = TrendResponse(venue_id="abc", venue_name="Riverside", weeks=0, snapshots=[])
        assert tr.weeks == 0
        assert tr.snapshots == []

    def test_prime_drift_readable_across_window(self):
        snaps = [
            _snapshot(date(2026, 3, 1), prime_pct=61.0),
            _snapshot(date(2026, 3, 8), prime_pct=61.5),
            _snapshot(date(2026, 3, 15), prime_pct=62.0),
            _snapshot(date(2026, 3, 22), prime_pct=62.5),
        ]
        tr = TrendResponse(venue_id="abc", venue_name="Riverside", weeks=4, snapshots=snaps)
        prime_pcts = [s.prime.actual_pct for s in tr.snapshots]
        # Sentinel detects: 4 consecutive weeks rising -- all diffs positive
        diffs = [prime_pcts[i + 1] - prime_pcts[i] for i in range(len(prime_pcts) - 1)]
        assert all(d > 0 for d in diffs), "3+ consecutive rising weeks = signal"


# ---------------------------------------------------------------------------
# FORECAST: prefix behavior
# ---------------------------------------------------------------------------
class TestForecastNotePrefix:

    def test_forecast_note_identified_by_prefix(self):
        notes = [
            "Labor 3.2pp over target -- driven by FOH overtime.",
            "FORECAST: Prime trending +0.4pp/week for 3 weeks. Projected 63.2% week ending 2026-04-05. Action: cap FOH OT.",
            "Food cost spike traced to Sysco protein invoices.",
        ]
        forecast_notes = [n for n in notes if n.startswith("FORECAST:")]
        assert len(forecast_notes) == 1
        assert "63.2%" in forecast_notes[0]

    def test_non_forecast_notes_excluded(self):
        notes = ["Labor over target.", "Food cost high.", "New chef training week."]
        forecast_notes = [n for n in notes if n.startswith("FORECAST:")]
        assert forecast_notes == []

    def test_prefix_is_case_sensitive(self):
        # Lowercase variants must NOT match -- Quant looks for exact "FORECAST:"
        notes = [
            "forecast: lowercase prefix.",
            "Forecast: mixed case prefix.",
            "FORECASTS: plural does not count.",
        ]
        forecast_notes = [n for n in notes if n.startswith("FORECAST:")]
        assert forecast_notes == []

    def test_no_signal_forecast_note_format(self):
        note = "FORECAST: No sustained trend detected in 4-week window as of 2026-03-22."
        assert note.startswith("FORECAST:")
        assert "No sustained trend" in note

    def test_signal_forecast_note_contains_required_fields(self):
        note = (
            "FORECAST: Prime cost trending +0.4pp/week for 3 consecutive weeks. "
            "Projected 63.2% week ending 2026-04-05. "
            "Driver: labor overtime. Action: cap FOH overtime at 0 hours Saturday."
        )
        assert note.startswith("FORECAST:")
        assert "Projected" in note
        assert "Action" in note
        assert "week ending" in note
