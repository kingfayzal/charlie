# Charlie — PrimeOps Agentic OS

A multi-agent AI system that gives multi-unit restaurant Directors of Operations a single, conversational view of their prime cost — across fragmented data sources, in plain English, in the time it takes to ask a question.

## About the Builder

I'm Fayzal. I build agentic AI systems and the data infrastructure underneath them.

Before this, I built **Sally** — an internal AI chatbot deployed at a previous role. The architectural pattern I'm using in Charlie (a routing concierge over specialist agents reading from a unified data layer) is a direct evolution of what Sally taught me: agents need narrow, well-bounded jobs and clean data underneath them, or they hallucinate confidently.

I captained the team that won the **MIT Business Hackathon** ($3,000 cash plus enterprise access to Stack AI), and I'm completing an **ML Engineering certification** to deepen the systems side of how I think about model orchestration and deployment.

I'm applying to Klaviyo's ARIA team because the concierge-plus-specialists pattern in Charlie is exactly the pattern ARIA's role description points at — agents that take actions, chain tasks, integrate with internal systems, and stay in a human-in-the-loop. Charlie is customer-facing; ARIA is internal. The architecture transfers cleanly.

## Problem Statement

I sat down with the Director of Operations of a Cambridge hospitality group. He runs reporting for the group's leadership and owners and described his work like this: every morning he wishes he could open one place that just told him *"here's what happened yesterday, here's what's coming today, here's what to worry about next week."* Instead, he reconciles data across Toast, Square, 7shifts, OpenTable, Eventbrite, Triple Seat, Paychex, and Basecamp by hand.

He had tried three platforms before me. All three promised forecasting and lost his trust because, in his words, *"the predictions weren't accurate at all."* When I asked what would have to be true for a tool to replace the spreadsheet ritual, his answer was unambiguous:

> *"I'd rather do the entire thing by hand than get 50%. A platform that does half the job adds complexity instead of removing it."*

That conversation defined Charlie's design constraint: don't ship 50%. Either the number is right, or the system tells the operator the data isn't ready and refuses to compute.

**Why prime cost specifically.** Prime cost — labor plus food, as a percentage of net sales — is the single most important number a multi-unit operator tracks. It runs 55–65% of revenue at most operators, which means almost all of a restaurant's controllable spend lives inside that one ratio. Industry-wide profit margins hover around 5%, so a three-point prime cost variance can erase roughly 60% of profit. Across a ten-venue group, the difference between catching a slip on Monday morning versus Wednesday afternoon compounds across labor reschedules, vendor calls, and menu decisions.

What success looks like is small and specific. The DoO opens the app Monday morning. He sees which venues missed prime cost last week and why. He asks *"is this a real trend?"* and gets back a forecast for next week with one preventive action attached. He moves on.

## Solution Overview

Charlie ingests three CSVs (POS daily sales, labor summary, purchases), runs them through an entity-resolution layer that maps source-system IDs to universal venue IDs, and computes weekly prime cost variance in deterministic Python. Six AI agents — one router and five specialists — sit on top of that data engine and narrate it conversationally through a single chat sidebar.

The deliberate split is math in Python, narration in LLM. Pandas and SQL produce the numbers; Gemini explains them. Agents physically cannot hallucinate financial figures because they read from the data engine through a tightly scoped tool layer, not from training data. Every percentage that reaches the operator was computed by `app/engine/cruncher.py` and round-tripped through a typed Pydantic schema. For a product where prime cost discipline determines profitability, this isn't a tradeoff — it's a requirement.

The most distinctive piece is the forecast-validation loop. When Sentinel detects a multi-week trend and projects next week, it writes a context note prefixed with the literal string `FORECAST:`. A week later, when the operator asks Quant about that venue, Quant scans the venue's notes for `FORECAST:` and grades the previous week's call as **HIT** (within 1pp), **MISS** (outside 1pp), or **PREVENTED** (operator took the recommended action and the metric improved). The DoO's complaint about prior tools was that they overpromised and never closed the loop. The validation loop exists so Charlie doesn't repeat that mistake.

## AI Integration

**Models.** Google ADK (Agent Development Kit) with **Gemini 2.5 Flash** for every agent. Flash, not Pro, was a deliberate latency call. The workload is high-frequency, short-context, and conversational — operators want chat-app speed, not research-report speed. A 30-second response to *"how is Central Ave?"* fails the use case.

**Agents.**

| Agent | Role |
|---|---|
| Concierge | Root agent. Resolves venue names, routes every query to the right specialist, handles greetings and ambiguous multi-venue questions. |
| Quant | Prime cost variance analysis. Reads the weekly brief, identifies the primary driver, validates any prior `FORECAST:` notes (HIT / MISS / PREVENTED), gives one recommendation. |
| Labor | BOH/FOH role-level breakdown. Surfaces overtime bleeds, names the specific role and shift to cut, estimates dollar impact. |
| Food Cost | Purchases by category and vendor. Flags vendor-concentration risk above 60% of food spend, recommends one purchasing action. |
| Benchmark | Cross-venue ranking. Orders all venues by prime cost variance, names the venue that needs immediate attention and why. |
| Sentinel | Forward-looking trend detection. Reads 4–8 weeks of history, requires 3+ consecutive weeks moving the same direction before forecasting, projects next week's metric and dollar impact, writes a `FORECAST:` note. |

**Patterns used.**

- **Hierarchical orchestration via `AgentTool`.** Concierge wraps each specialist as a callable tool, so routing is a tool selection rather than a string match. The routing decision lives inside the LLM's reasoning step and the agent boundary is explicit in code.
- **Tools scoped per agent.** Labor only sees `get_labor_drilldown`; Food Cost only sees `get_food_drilldown`; Sentinel is the only agent with access to `/trend/{venue_id}`. Specialists cannot accidentally call into each other's data shape.
- **Multi-step reasoning.** Concierge → Specialist → 1–3 tool calls → response synthesis. Most queries finish in two to four model turns end-to-end.
- **Persistent agent memory via context notes.** Every specialist calls `save_context_note` after producing analysis; notes persist on the venue record and surface in the next `/brief` payload.
- **The `FORECAST:` prefix convention.** A load-bearing string. Sentinel writes notes prefixed `FORECAST:`; Quant scans for that exact prefix the following week. No vector store, no semantic match — a literal string is the simplest thing that works.
- **Tightly bounded prompts with explicit hard rules.** Every specialist prompt ends with explicit prohibitions: *"never calculate percentages yourself,"* *"never forecast from a single data point,"* *"never skip step 6."* Rigidity is the point.

**Tradeoffs.**

- **Flash over Pro.** Lower reasoning ceiling, but the agents don't need a high one — the math is already done. Operators get sub-three-second responses on most queries.
- **No RAG over context notes.** At current data volume (a few notes per venue per week), linear reads are faster, cheaper, and more predictable than embeddings. Adding a vector store would be an answer to a problem that doesn't exist yet.
- **Hard rules in prompts vs. flexibility.** Chose rigidity. For a financial product, agents that physically can't hallucinate beats agents that occasionally do. The cost is occasional verbosity; the benefit is correctness.
- **Sentinel's three-consecutive-weeks threshold.** Conservative on purpose. The customer rejected three prior platforms whose models *"weren't accurate at all."* False alarms destroy trust faster than missed calls. A noisy forecaster gets ignored after the first wrong call; a quiet one earns the next conversation.

**Where AI exceeded expectations.** Sentinel's forecast quality given a four-week trend window. Gemini extrapolates direction and magnitude correctly more often than expected, with realistic dollar-impact estimates that hold up against the deterministic math. Concierge also handles ambiguous questions well (*"is it labor or food?"*) — it correctly delegates to Quant first, lets Quant identify the primary driver, and the operator drills down from there.

**Where it fell short.** Multi-venue questions (*"what should I worry about across all venues?"*) initially failed because Sentinel was scoped per venue and didn't know to fan out. Fix was tightening the multi-venue block in the Concierge prompt and exposing `list_venues` as a first-class tool. Lesson: agents don't generalize across data shapes the way humans do. Orchestration patterns have to be taught explicitly, not implied.

## Architecture / Design Decisions

**Stack.**

- **Backend:** FastAPI on Python 3.11, async throughout. Pandas for crunching.
- **Database:** SQLite with `aiosqlite` for local development; Postgres on Cloud SQL for production. Schema is identical via SQLAlchemy.
- **Frontend:** React + Vite + TypeScript. Two-pane layout — dashboard on the left, chat sidebar on the right. No router, no state management library.
- **AI:** Google ADK with Gemini 2.5 Flash via Vertex AI.
- **Deployment:** Cloud Run via Dockerfile, multi-stage build, non-root user. GCS for production CSV ingestion.

**Data flow.**

```
3 CSVs (POS, Labor, Purchases)
    → Adapter (parse + normalize)
    → Resolver (source IDs → universal venue IDs)
    → Cruncher (weekly prime/labor/food % + variance + drivers)
    → SQL persistence
    → /brief, /drilldown, /compare, /trend endpoints
    → ADK agents (read-only tool calls)
    → Concierge → Specialist → Operator
```

**Six key decisions.**

1. **Math in Python, narration in LLM.** The cruncher computes every number; agents read those numbers and explain them. Cost: more code, more typed schemas. Benefit: numbers can be proven correct, and the LLM physically cannot hallucinate them. Non-negotiable for a financial product.
2. **Entity resolution as the moat.** A separate `app/engine/resolver.py` module maps source-system IDs (MarketMan's `heathfield`, `3t0862`, `downtown_hub`) to universal venue UUIDs. Without this layer, *"Central Ave"* in Toast and `heathfield` in MarketMan are unrelated strings, and prime cost is uncomputable for any operator using more than one upstream system.
3. **DataReadinessError over partial answers.** When labor or purchase data is missing for a venue in the requested week, the cruncher raises a 422 with a specific message about what's missing. It does not compute a partial number. The customer's exact words: *"I'd rather do the whole thing by hand than get 50%."*
4. **The `FORECAST:` prefix is load-bearing.** A simple string convention beats a complex retrieval system at this data volume. Sentinel writes notes prefixed `FORECAST:`; Quant scans for that prefix next week. No vector store, no embeddings — just a literal string match. When data volume justifies retrieval, retrieval is the right answer; until then, simpler is correct.
5. **Async everywhere.** FastAPI is async, the database session is async, and ADK tools call back into the API via `httpx.AsyncClient`. The agents and the API share a uvicorn worker; a blocking call on the agent path would deadlock that worker against itself. Hit this early; moving venue lookups onto async resolved it.
6. **Single-page frontend, two panes.** Resisted the urge to ship a full admin app with venue settings, target editing, and historical week navigation. The DoO's morning ritual is *"what happened, what's coming, what should I worry about."* The app does that. One thing, well.

**Open work.**

- The synthetic dataset has embedded narratives — Central Ave food cost drift, Riverside Friday under-scheduling, Downtown clean — that drive the demo cleanly. Real customer data will be messier. The entity resolver will need richer fuzzy matching (e.g., when MarketMan exports `heathfield-2` after a venue rebrand and 7shifts still calls it `Central Ave`).
- Demo runs against SQLite. Production runs against Postgres on Cloud Run. Schema is identical via SQLAlchemy, and the migration path is `alembic upgrade head` against the Cloud SQL connection string in `.env`.
- A few of the venue resolution helpers in `app/ai/tools/venue_tools.py` still use synchronous `requests` rather than `httpx`. They work — they're called outside the hot path — but switching to async is on the punch list.

## What AI helped me do faster — and where it got in the way

**Faster.** Scaffolding the agent layer (Claude Code wrote the first cut of all five specialists, including the prompt structure that I then edited heavily). CSV adapters and the column-aliasing logic for messy real-world headers. React frontend boilerplate — the two-pane layout, the chat plumbing, the upload form. Prompt tightening, where LLMs are unreasonably good at writing prompts for other LLMs. Test scaffolding for the cruncher.

**In the way.** ADK has a circular import pattern that bit me: agents instantiate at import time and reference each other through `AgentTool`, and the auto-generated import structure produced cycles that no amount of *"just fix the imports"* prompting resolved. Manual refactoring of the module boundaries was the only way through. AI tools also over-engineered when given an ambiguous prompt — at one point I rejected a Vertex RAG corpus suggestion for a problem that doesn't yet exist, because the agent saw *"context notes"* and reached for embeddings without checking the volume. The synthetic data generation was its own loop: the first three runs produced plausible-looking but internally inconsistent CSVs, where Toast sales didn't reconcile with MarketMan invoices for the same week. The cruncher refused to compute and threw a `DataReadinessError` — the feature working as designed — but it took manual seed tuning to get a coherent demo dataset.

I now treat AI tools as a fast, occasionally brilliant, consistently overconfident collaborator. Outline the architecture myself, let AI write 70% of the code, audit aggressively. Letting AI architect is where complexity creeps in.

## Getting Started

**Prerequisites:** Python 3.11+, Node 18+, GCP project with Vertex AI enabled (only needed for the agent layer; the data engine works standalone with no GCP credentials).

```bash
git clone <repo-url>
cd charlie

# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — set GOOGLE_CLOUD_PROJECT and GOOGLE_APPLICATION_CREDENTIALS

# Seed venues + entity-resolution mappings
python seed_db.py

# Run the API server (port 8080 — must match what the frontend expects)
uvicorn app.main:app --reload --port 8080

# In a second terminal, run the frontend
cd frontend
npm install
npm run dev
# http://localhost:5173

# Optional: ADK web UI for direct agent testing
adk web adk_agents
```

The port matters. The frontend's `App.tsx` hardcodes `127.0.0.1:8080`, so uvicorn must run on 8080.

## Demo

The dashboard auto-loads with the seeded data ready to inspect. To see the upload form, click **Upload New Week** in the dashboard header — note that the upload flow currently returns to the populated dashboard rather than ingesting fresh data. This is intentional for the demo build; the bundled CSVs under `data/` are the source of truth.

Five questions to ask the Concierge in the chat sidebar:

- *"How is Central Ave performing?"* — Quant surfaces prime cost variance and the primary driver, with one recommendation.
- *"Should I be worried about Central Ave next week?"* — Sentinel runs trend detection across the trailing weeks and forecasts next week, writing a `FORECAST:` note.
- *"How did Central Ave perform last week?"* (after the previous question) — Quant validates the prior `FORECAST:` note as HIT, MISS, or PREVENTED.
- *"Which venue needs the most attention?"* — Benchmark ranks all three venues by prime cost variance and names the one to act on first.
- *"Why is food cost high at Central Ave?"* — Food Cost drilldown by vendor and category, with a vendor-concentration check.

The `agent_name` badge appears above each chat response, making the routing layer visible — you can watch the Concierge hand off to a different specialist on each question.

## Testing / Error Handling

Run `pytest tests/ -v` to execute the suite. Tests cover the deterministic core — the cruncher, the adapter, and the trend route. The agents' behavior is not unit-tested directly, but their inputs are, which means every number an agent can quote has been verified.

**Named errors with HTTP codes:**

- **`DataReadinessError` (422)** — partial data is refused with a specific message about what source is missing for which venue, rather than computed wrong. The error payload includes `missing_sources` so the operator knows exactly which upstream system to check.
- **`MappingNotFoundError` (422)** — when an unknown source-system ID appears in a CSV (e.g., a new venue not yet in the resolver), the request fails fast and the unmapped ID is surfaced. Unknown IDs are forced to operator attention rather than silently dropped.

**Other deliberate handling:**

- **Async tool timeouts.** ADK tools call the data engine over `httpx` with a 20-second timeout. If the engine hangs, agents degrade gracefully with a structured error rather than timing out the chat session.
- **Sentinel honesty rule.** When no multi-week trend is detected, Sentinel says so plainly and writes a note like `FORECAST: No sustained trend detected in 4-week window`. It does not invent risk to seem useful.

**Edge cases considered:** partial venue names (Concierge uses fuzzy matching via `resolve_venue_by_name`); multi-venue questions (Concierge fans out via `list_venues`); no-venue questions (Concierge calls `list_venues` and asks the operator which one); single-week spikes (Sentinel rejects as noise rather than forecasting); greetings (Concierge responds directly without burning a tool call).

## Future Improvements

In priority order:

1. **Real API integrations replacing CSVs.** Direct connections to Toast, Square, 7shifts, Paychex, OpenTable, Eventbrite, Triple Seat — the actual stack the pilot DoO uses. CSV upload was the right MVP because it got the agents working against real-shape data fast; APIs are the right product, and the adapter layer was built with that switch in mind.
2. **Proactive Monday brief delivery.** Pre-computed weekly brief delivered via WhatsApp or email at 7am Monday. The DoO explicitly asked for *"a digest in my inbox in the morning."* The architecture supports it — Quant can already compose the brief on demand — what's missing is a Cloud Scheduler trigger and a Twilio sender.
3. **Mobile-responsive layout.** The two-pane desktop layout doesn't reflow well on a phone. The DoO who reads the brief on the train gets a worse experience than at his desk.
4. **Vector search over context notes.** Once notes per venue cross roughly fifty, linear reads stop being adequate and the `FORECAST:` prefix scan stops scaling. Vertex AI RAG with a GCS-backed corpus is the right pattern when the data justifies it. Today, it doesn't.
5. **Sentinel autonomy graduation.** Currently observe-only — it forecasts and recommends, the operator acts. Once forecast accuracy is established (HIT rate above some threshold), the natural next step is propose-and-approve on bounded actions: draft a GM message cutting Saturday FOH hours, surface it to the operator, one tap to send. Human-in-the-loop stays; friction drops.

## Acknowledgments

- Built on **Google ADK** (Agent Development Kit) and **Gemini 2.5 Flash** via Vertex AI.
- Frontend: **React**, **Vite**, **TypeScript**.
- Backend: **FastAPI**, **SQLAlchemy** (async), **Pandas**.
- Inspired by an in-depth conversation with the Director of Operations of a Cambridge hospitality group; the group's name is kept private at this stage of the engagement.
- Prime cost framing draws on the National Restaurant Association's industry data (cited via BentoBox restaurant benchmarks) and the Oracle / Studio by Informa TechTarget 2026 survey of 1,254 restaurant leaders (cited via Restaurant Dive).
- No proprietary code from any current or former employer is used in this submission. No live credentials, API keys, or service account JSONs are included; `.env.example` uses placeholders only.
