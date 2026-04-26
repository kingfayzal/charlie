"""
PrimeOps ADK Web entry point.

`adk web` looks for a variable named `root_agent` in this file.
The concierge_agent is the root — it routes to specialist sub-agents.

Prerequisites:
  - FastAPI server must be running on port 8000 (the agent tools call back to it)
  - GOOGLE_GENAI_USE_VERTEXAI, GOOGLE_CLOUD_PROJECT, GOOGLE_CLOUD_LOCATION
    must be set in the environment (or .env loaded before launching adk web)
"""

import os
import sys

# Make sure the Neo package root is on sys.path so `app.*` imports resolve
_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _root not in sys.path:
    sys.path.insert(0, _root)

# Configure Vertex AI before importing any agent (agents instantiate at import time)
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "1")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "chartered-ai-prod")
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "us-central1")

from app.ai.agents.concierge import concierge_agent  # noqa: E402

root_agent = concierge_agent
