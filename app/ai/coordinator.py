"""
PrimeOps Agentic OS — AI Orchestrator
Manages the multi-agent hierarchy using the Vertex AI Python SDK.

Agents:
  1. Concierge Agent: The entry point. Interprets user intent, extracts venue/date info,
     and routes to the appropriate specialist agent.
  2. Quant Agent: The financial specialist. Uses Function Calling to hit the internal
     FastAPI endpoints (`/ingest`, `/brief/{venue_id}`) and narrates the deterministic data.
"""

import json
import os
from typing import Any, Dict, List
import requests

from vertexai.generative_models import (
    GenerativeModel,
    Tool,
    FunctionDeclaration,
    Part
)
import vertexai

# Define functions for QuantAgent
get_weekly_brief_func = FunctionDeclaration(
    name="get_weekly_brief",
    description="Fetch the weekly Prime Cost and variance brief for a specific venue.",
    parameters={
        "type": "object",
        "properties": {
            "venue_id": {
                "type": "string",
                "description": "The UUID of the venue."
            },
            "week_ending": {
                "type": "string",
                "description": "Optional week ending date (YYYY-MM-DD)."
            }
        },
        "required": ["venue_id"]
    }
)

get_labor_drilldown_func = FunctionDeclaration(
    name="get_labor_drilldown",
    description="Fetch role-level labor and overtime breakdown for a specific venue.",
    parameters={
        "type": "object",
        "properties": {
            "venue_id": {
                "type": "string",
                "description": "The UUID of the venue."
            },
            "week_ending": {
                "type": "string",
                "description": "Optional week ending date (YYYY-MM-DD)."
            }
        },
        "required": ["venue_id"]
    }
)

finance_tool = Tool(
    function_declarations=[get_weekly_brief_func, get_labor_drilldown_func],
)


class QuantAgent:
    """Specialist agent for financial synthesis and data retrieval."""

    def __init__(self):
        self._live = os.environ.get("VERTEX_LIVE", "false").lower() == "true"
        if self._live:
            try:
                # Use a specific version for Vertex AI to prevent 404s
                self.model = GenerativeModel("gemini-1.5-pro-001", tools=[finance_tool])
            except Exception as e:
                print(f"[QuantAgent] Failed to init live model: {e}")
                self._live = False

    def _call_api(self, endpoint: str, venue_id: str, week_ending: str = None) -> dict:
        url = f"http://127.0.0.1:8000{endpoint}/{venue_id}"
        if week_ending:
            url += f"?week_ending={week_ending}"
        try:
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"error": str(e)}

    def process(self, query: str, context: Dict[str, Any]) -> str:
        """
        Executes the Quant Agent reasoning loop.
        """
        print(f"[Quant Agent] Analyzing request: '{query}' with context {context}")
        
        if not self._live:
            # Simulated fallback for tests without GCP auth
            venue_id = context.get("venue_id", "11111111-1111-1111-1111-111111111111")
            brief = self._call_api("/brief", venue_id)
            if "labor" in query.lower():
                drilldown = self._call_api("/drilldown/labor", venue_id)
                return f"I've analyzed the labor drilldown. Total labor cost is ${drilldown.get('total_labor_cost')} with ${drilldown.get('total_overtime_cost')} in overtime."
            return f"Prime Cost was {brief.get('prime', {}).get('actual_pct')}% this week. {brief.get('driver_detail')}"

        try:
            chat = self.model.start_chat()
            prompt = f"Context: {json.dumps(context)}. User query: {query}"
            response = chat.send_message(prompt)
            
            if response.function_call:
                func = response.function_call
                if func.name == "get_weekly_brief":
                    data = self._call_api("/brief", func.args.get("venue_id"), func.args.get("week_ending"))
                elif func.name == "get_labor_drilldown":
                    data = self._call_api("/drilldown/labor", func.args.get("venue_id"), func.args.get("week_ending"))
                else:
                    data = {"error": "Unknown function"}
                
                response = chat.send_message(
                    Part.from_function_response(
                        name=func.name,
                        response={"content": data}
                    )
                )
                
            return response.text
        except Exception as e:
            print(f"[QuantAgent] Live generation failed: {e}")
            return f"I encountered an error communicating with the Vertex AI models: {e}"


class ConciergeAgent:
    """The routing agent that intercepts user queries and hands off to specialists."""

    def __init__(self):
        self._live = os.environ.get("VERTEX_LIVE", "false").lower() == "true"
        if self._live:
            try:
                self.model = GenerativeModel(
                    "gemini-1.5-flash-001",
                    system_instruction="You are a routing agent. Return JSON with 'target_agent' ('quant' or 'general') and 'extracted_params' (e.g. venue_id, week_ending)."
                )
            except Exception as e:
                print(f"[ConciergeAgent] Failed to init live model: {e}")
                self._live = False

    def route_query(self, query: str) -> Dict[str, Any]:
        """Determine which agent should handle the request and extract parameters."""
        print(f"[Concierge] Routing query: '{query}'")
        
        if not self._live:
            if "cost" in query.lower() or "labor" in query.lower() or "briefing" in query.lower():
                return {
                    "target_agent": "quant",
                    "extracted_params": {
                        "venue_id": "11111111-1111-1111-1111-111111111111" 
                    }
                }
            return {"target_agent": "general", "extracted_params": {}}
            
        try:
            response = self.model.generate_content(
                f"Extract intent and parameters from: {query}\n\n"
                f"We have venue 'Downtown' (ID: 11111111-1111-1111-1111-111111111111)."
            )
            text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
            return json.loads(text)
        except Exception as e:
            print(f"[Concierge] LLM Routing failed: {e}")
            return {
                "target_agent": "quant",
                "extracted_params": {"venue_id": "11111111-1111-1111-1111-111111111111"}
            }


class Coordinator:
    """
    The main Orchestrator class. 
    Manages state, history, and the handoff between agents.
    """

    def __init__(self):
        self.concierge = ConciergeAgent()
        self.quant = QuantAgent()
        self.chat_history: List[Dict[str, str]] = []

    def handle_message(self, user_message: str) -> str:
        """Process an incoming message from the user (e.g., via WhatsApp)."""
        
        self.chat_history.append({"role": "user", "content": user_message})
        
        # 1. Concierge determines intent
        routing_decision = self.concierge.route_query(user_message)
        
        # 2. Handoff to Specialist
        if routing_decision["target_agent"] == "quant":
            response = self.quant.process(
                query=user_message, 
                context=routing_decision["extracted_params"]
            )
        else:
            response = "I can help route you to the right department. Could you specify if you need financial insights or operational help?"
            
        self.chat_history.append({"role": "assistant", "content": response})
        return response

# Example usage:
if __name__ == "__main__":
    orchestrator = Coordinator()
    print(orchestrator.handle_message("Give me the weekly briefing for Downtown."))
    print("---")
    print(orchestrator.handle_message("Drill down into labor overtime, please."))
