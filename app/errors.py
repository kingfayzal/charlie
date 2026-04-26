"""
PrimeOps Agentic OS — Custom Exceptions & FastAPI Error Handlers

Business Rule: If a venue has Sales data but no Labor or Purchases data
for the period, we MUST return a 422 with a specific, actionable message.
We never calculate partial (wrong) numbers.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------
class DataReadinessError(Exception):
    """
    Raised when data is incomplete for a venue.

    Business Rule from CONTEXT.md:
      "If a venue ID is missing in one system, the engine must flag a
       'Data Readiness Error' rather than calculating a partial (wrong) number."
    """

    def __init__(
        self,
        venue_name: str,
        detail: str,
        missing_sources: list[str] | None = None,
        missing_days: list[str] | None = None,
    ):
        self.venue_name = venue_name
        self.detail = detail
        self.missing_sources = missing_sources or []
        self.missing_days = missing_days or []
        super().__init__(self.detail)


class MappingNotFoundError(Exception):
    """
    Raised when an external ID cannot be resolved to a Universal Venue ID.
    This is a critical failure — it means the Entity Resolution Layer has a gap.
    """

    def __init__(self, external_id: str, source_system: str):
        self.external_id = external_id
        self.source_system = source_system
        self.detail = (
            f"No mapping found for external_id='{external_id}' "
            f"in source_system='{source_system}'. "
            f"Add a mapping via the admin API before ingesting data."
        )
        super().__init__(self.detail)


class VenueNotFoundError(Exception):
    """Raised when a venue_id does not exist in the venues table."""

    def __init__(self, venue_id: str):
        self.venue_id = venue_id
        self.detail = f"Venue '{venue_id}' not found."
        super().__init__(self.detail)


# ---------------------------------------------------------------------------
# FastAPI Exception Handlers
# ---------------------------------------------------------------------------
def register_exception_handlers(app: FastAPI) -> None:
    """Register all custom exception handlers on the FastAPI app."""

    @app.exception_handler(DataReadinessError)
    async def data_readiness_handler(request: Request, exc: DataReadinessError):
        return JSONResponse(
            status_code=422,
            content={
                "error": "data_readiness_error",
                "venue_name": exc.venue_name,
                "detail": f"Incomplete data for {exc.venue_name}. {exc.detail}",
                "missing_sources": exc.missing_sources,
                "missing_days": exc.missing_days,
            },
        )

    @app.exception_handler(MappingNotFoundError)
    async def mapping_not_found_handler(request: Request, exc: MappingNotFoundError):
        return JSONResponse(
            status_code=422,
            content={
                "error": "mapping_not_found",
                "external_id": exc.external_id,
                "source_system": exc.source_system,
                "detail": exc.detail,
            },
        )

    @app.exception_handler(VenueNotFoundError)
    async def venue_not_found_handler(request: Request, exc: VenueNotFoundError):
        return JSONResponse(
            status_code=404,
            content={
                "error": "venue_not_found",
                "venue_id": exc.venue_id,
                "detail": exc.detail,
            },
        )
