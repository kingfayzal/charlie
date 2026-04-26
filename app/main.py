"""
PrimeOps Agentic OS — FastAPI Application Entry Point

The API layer that ADK Agents call as Tools.
Deterministic math lives in app/engine/cruncher.py.
Stochastic reasoning lives in the ADK agents (not here).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.errors import register_exception_handlers
from app.routes import ingest, upload, brief, drilldown, food_drilldown, compare, context, venues, chat


# ---------------------------------------------------------------------------
# Lifespan: startup / shutdown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    yield


# ---------------------------------------------------------------------------
# App Factory
# ---------------------------------------------------------------------------
app = FastAPI(
    title="PrimeOps Agentic OS",
    description=(
        "Data Engine & Mapping Layer for Restaurant Operations. "
        "Provides deterministic financial calculations and entity resolution "
        "as tool-endpoints for Google ADK agents."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — permissive for dev, lock down for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register custom exception handlers (DataReadinessError → 422, etc.)
register_exception_handlers(app)

# Register route modules
app.include_router(ingest.router)
app.include_router(upload.router)
app.include_router(venues.router)
app.include_router(brief.router)
app.include_router(drilldown.router)
app.include_router(food_drilldown.router)
app.include_router(compare.router)
app.include_router(context.router)
app.include_router(chat.router)


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------
@app.get("/health", tags=["System"])
async def health_check():
    """Health check for Cloud Run and load balancers."""
    return {
        "status": "healthy",
        "service": "PrimeOps Data Engine",
        "version": "1.0.0",
        "endpoints": [
            "POST /ingest", "POST /upload",
            "GET /venues",
            "GET /brief/{venue_id}",
            "GET /drilldown/labor/{venue_id}", "GET /drilldown/food/{venue_id}",
            "GET /compare/venues",
            "PATCH /context/{venue_id}",
            "POST /chat",
        ],
    }


# ---------------------------------------------------------------------------
# Local Dev Runner
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=True)
