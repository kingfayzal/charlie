"""
PrimeOps Agentic OS — POST /chat
Runs the user message through the ADK Runner (Concierge → specialist agents).
Session continuity is maintained via the session_id supplied by the frontend.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from google.genai import types

from app.schemas import ChatRequest, ChatResponse
from app.ai.runner import get_runner
from app.ai.session import session_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Agentic Chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Send a message to the PrimeOps multi-agent system.

    The Concierge Agent receives the message, resolves venue context if provided,
    and delegates to the appropriate specialist (Quant, Labor, FoodCost, or Benchmark).
    Session history is maintained per session_id so the conversation is stateful.
    """
    runner = get_runner()

    if runner is None:
        return ChatResponse(
            reply=(
                "The AI agents are not configured yet. "
                "Set GOOGLE_CLOUD_PROJECT and GOOGLE_APPLICATION_CREDENTIALS in your .env file, "
                "then restart the server."
            ),
            agent_name="system",
        )

    # Inject selected venue as a hint if the dashboard has one selected
    message = request.message
    if request.venue_id:
        message = f"[Context: venue_id={request.venue_id}] {message}"

    content = types.Content(
        role="user",
        parts=[types.Part(text=message)],
    )

    # Ensure session exists — InMemorySessionService raises if not found
    existing = await session_service.get_session(
        app_name="primeops",
        user_id="operator",
        session_id=request.session_id,
    )
    if existing is None:
        await session_service.create_session(
            app_name="primeops",
            user_id="operator",
            session_id=request.session_id,
        )

    reply = ""
    agent_name = "concierge"

    try:
        async for event in runner.run_async(
            user_id="operator",
            session_id=request.session_id,
            new_message=content,
        ):
            if event.is_final_response() and event.content and event.content.parts:
                reply = event.content.parts[0].text or ""
                agent_name = getattr(event, "author", "concierge") or "concierge"
                break
    except Exception as e:
        err = str(e)
        logger.error("[chat] Agent exception: %s", err)
        if "NOT_FOUND" in err and "Publisher Model" in err:
            reply = (
                "Gemini models are not yet enabled on this GCP project. "
                "In the Cloud Console, go to Vertex AI -> Model Garden and enable access "
                "to Gemini models for project 'chartered-ai-prod', then restart the server."
            )
        else:
            reply = f"Agent error: {err[:300]}"
        agent_name = "system"

    return ChatResponse(reply=reply, agent_name=agent_name)
