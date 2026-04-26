"""
PrimeOps — ADK Runner

Initialises Vertex AI and creates the ADK Runner singleton.
Lazy-initialised so import failures (e.g. missing GCP credentials) don't crash the server —
the chat route degrades gracefully instead.
"""

from __future__ import annotations

import logging

from app.config import get_settings

logger = logging.getLogger(__name__)

_runner = None


def get_runner():
    """
    Return the ADK Runner singleton, initialising it on first call.
    Returns None if GCP credentials are not configured or initialisation fails.
    """
    global _runner
    if _runner is not None:
        return _runner

    settings = get_settings()
    if not settings.google_cloud_project:
        logger.warning(
            "[ADK] GOOGLE_CLOUD_PROJECT is not set. "
            "Set it in .env to enable the AI agents."
        )
        return None

    try:
        import os
        import vertexai
        from google.adk.runners import Runner

        from app.ai.agents.concierge import concierge_agent
        from app.ai.session import session_service

        # Tell google-genai to use Vertex AI (service account) instead of API key
        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "1")
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", settings.google_cloud_project)
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", settings.google_cloud_region)

        vertexai.init(
            project=settings.google_cloud_project,
            location=settings.google_cloud_region,
        )

        _runner = Runner(
            agent=concierge_agent,
            app_name="primeops",
            session_service=session_service,
        )
        logger.info(
            "[ADK] Runner initialised — project=%s region=%s",
            settings.google_cloud_project,
            settings.google_cloud_region,
        )
        return _runner

    except Exception as e:
        logger.error("[ADK] Runner initialisation failed: %s", e)
        return None
