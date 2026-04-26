"""
PrimeOps ADK Tools — Venue resolution

Used by the Concierge Agent to map human venue names to UUIDs before
delegating to specialist agents. Must be called before any venue-specific tool.
"""

from __future__ import annotations

import requests

from app.config import get_settings

_BASE = get_settings().api_base_url


def list_venues() -> dict:
    """
    List all venues with their IDs, names, and targets.
    Call this when you need to show the operator what venues are available,
    or to resolve an ambiguous venue reference.
    """
    try:
        resp = requests.get(f"{_BASE}/venues", timeout=10)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def resolve_venue_by_name(name: str) -> dict:
    """
    Resolve a venue name (full or partial, case-insensitive) to its UUID.
    Always call this before passing venue_id to any specialist agent or tool.
    Returns {"venue_id": "...", "venue_name": "..."} on success,
    or {"error": "...", "available_venues": [...]} if not found.
    """
    try:
        resp = requests.get(f"{_BASE}/venues", timeout=10)
        venues = resp.json().get("venues", [])
    except Exception as e:
        return {"error": str(e)}

    name_lower = name.strip().lower()
    for v in venues:
        if name_lower in v["name"].lower() or v["name"].lower() in name_lower:
            return {"venue_id": v["id"], "venue_name": v["name"]}

    return {
        "error": f"No venue found matching '{name}'.",
        "available_venues": [v["name"] for v in venues],
    }
