"""
PrimeOps ADK Tools — API callers

Each function is an async callable that ADK registers as a tool for Gemini.
They make async HTTP calls to the running FastAPI server using httpx so they
never block the event loop (avoids deadlock when the tool calls back to the
same uvicorn worker that is serving the /chat request).
"""

from __future__ import annotations

import httpx

from app.config import get_settings

_BASE = get_settings().api_base_url


async def _get(path: str, params: dict | None = None) -> dict:
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(f"{_BASE}{path}", params=params or {})
            return resp.json()
    except Exception as e:
        return {"error": str(e)}


async def _patch(path: str, payload: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.patch(f"{_BASE}{path}", json=payload)
            return resp.json()
    except Exception as e:
        return {"error": str(e)}


async def get_weekly_brief(venue_id: str, week_ending: str | None = None) -> dict:
    """
    Fetch the weekly Prime Cost and variance brief for a specific venue.
    Returns net_sales, labor %, food %, prime %, variances vs targets,
    primary_driver, driver_detail, and recent context notes.
    Always call this first for any financial or variance question.
    """
    return await _get(f"/brief/{venue_id}", {"week_ending": week_ending} if week_ending else None)


async def get_labor_drilldown(venue_id: str, week_ending: str | None = None) -> dict:
    """
    Fetch role-level BOH and FOH labor breakdown for a venue.
    Returns hours worked, overtime hours, estimated costs per role,
    and BOH/FOH aggregate summaries. Use for overtime or scheduling questions.
    """
    return await _get(f"/drilldown/labor/{venue_id}", {"week_ending": week_ending} if week_ending else None)


async def get_food_drilldown(venue_id: str, week_ending: str | None = None) -> dict:
    """
    Fetch purchase category and vendor spend breakdown for a venue.
    Returns total food cost, variance vs target, spend by category (Protein,
    Produce, Dairy, etc.) and by vendor. Use for food cost or purchasing questions.
    """
    return await _get(f"/drilldown/food/{venue_id}", {"week_ending": week_ending} if week_ending else None)


async def compare_all_venues(week_ending: str | None = None) -> dict:
    """
    Compare Prime Cost performance across all venues for a given week.
    Returns all venues ranked by prime cost variance (rank 1 = best performer).
    Use for cross-location benchmarking or "which venue is doing best/worst" questions.
    """
    return await _get("/compare/venues", {"week_ending": week_ending} if week_ending else None)


async def save_context_note(venue_id: str, note: str) -> dict:
    """
    Save an operational context note for a venue (persistent agent memory).
    Use this after every analysis to record the key finding. Examples:
    "Labor 3.2pp over target — driven by FOH overtime on Friday/Saturday."
    "Food cost spike traced to Sysco protein invoices, up 18% vs prior week."
    These notes are surfaced to future analyses via /brief.
    """
    return await _patch(f"/context/{venue_id}", {"note": note, "author": "agent"})
