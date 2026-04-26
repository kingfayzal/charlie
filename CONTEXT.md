# Part 1: The Antigravity Project Context

**Project Name:** PrimeOps Agentic OS
**Core Philosophy:** Separation of Concerns. Deterministic math is handled by Python/Pandas; Stochastic reasoning and narration are handled by Google ADK (Gemini).

## The Moat
The "Entity Resolution Layer." We must map disparate IDs from Toast (POS), 7shifts (Labor), and MarketMan (Purchases) to a single Universal Venue ID.

## Business Rules for Data Engine
- **Net Sales** is the denominator for all percentages.
- **Prime Cost** = (Actual Labor Cost + Actual Food Purchases) / Net Sales.
- **Labor Actuals** must include BOH and FOH role-level detail to catch overtime "bleeds."
- **Food Actuals for MVP** are "Purchases-to-Sales" (Total weekly invoices / Net Sales).
- **Entity Resolution:** If a venue ID is missing in one system, the engine must flag a "Data Readiness Error" rather than calculating a partial (wrong) number.

## Technical Stack
- **Backend:** FastAPI (Python 3.11+)
- **Database:** PostgreSQL (Cloud SQL)
- **Storage:** Google Cloud Storage (GCS)
- **AI:** Google Vertex AI / Agent Development Kit (ADK)
- **Communication:** Twilio API for WhatsApp Ingress/Egress.
