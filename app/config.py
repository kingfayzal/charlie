"""
PrimeOps Agentic OS — Configuration
Loads environment variables via Pydantic Settings.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database: SQLite for local dev, PostgreSQL (Cloud SQL via asyncpg) for production
    # Override with DATABASE_URL env var for production
    database_url: str = "sqlite+aiosqlite:///./primeops.db"

    # Sync URL for Pandas/cruncher operations (run in thread pool)
    @property
    def sync_database_url(self) -> str:
        """Convert async URL to sync for use in threaded cruncher operations."""
        return self.database_url.replace("+asyncpg", "+psycopg2")

    # Google Cloud
    gcs_bucket: str = "primeops-data"
    google_cloud_project: str = ""
    google_cloud_region: str = "us-central1"

    # ADK — base URL the agent tools use to call FastAPI endpoints
    api_base_url: str = "http://127.0.0.1:8000"

    # App
    debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    """Cached singleton for app settings."""
    return Settings()
