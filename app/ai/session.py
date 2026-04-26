"""
PrimeOps — ADK Session Service

InMemorySessionService for development. Sessions are keyed by (app_name, user_id, session_id).
The session_id comes from the frontend (stored in localStorage) so conversations
persist across page refreshes within a browser session.

For production: swap to a DatabaseSessionService backed by the existing PostgreSQL instance.
"""

from google.adk.sessions import InMemorySessionService

session_service = InMemorySessionService()
