# Architecture

FootballQ AI is split into two independently deployable parts that talk to
each other over HTTPS/JSON:

```
┌─────────────────────────────┐        HTTPS/JSON        ┌──────────────────────────────────┐
│  Frontend (Vercel Hobby)     │ ───────────────────────▶ │  API (Azure Functions, Python)    │
│  Next.js 14 App Router       │ ◀─────────────────────── │  Consumption plan, anonymous auth │
│  TypeScript + Tailwind +     │                           │  Pydantic-validated endpoints     │
│  Recharts + Zod              │                           └────────────────┬───────────────────┘
└───────────────────────────────┘                                            │
                                                                              │ parameterised SQL
                                                                              ▼
                                                              ┌──────────────────────────────────┐
                                                              │  Data layer                       │
                                                              │  Azure SQL (free offer) OR         │
                                                              │  in-memory LocalSeedDataStore      │
                                                              │  (zero-config fallback)            │
                                                              └──────────────────────────────────┘
```

## Frontend

Next.js 14 (App Router) renders seven pages: landing (`/`), Q Scout
(`/scout`), player comparison (`/compare`), similarity finder
(`/similarity`), tactical fit explorer (`/tactical-fit`), an architecture
explainer (`/architecture`), and an about/security page (`/about`). All API
calls go through `frontend/src/lib/api.ts`, which returns a discriminated
`ApiResult<T>` (`{ ok: true, data }` or `{ ok: false, error }`) so every page
can render loading, error, and empty states explicitly. Request payloads are
validated client-side with Zod schemas in `frontend/src/lib/schemas.ts` that
mirror the backend Pydantic models, so obviously invalid requests never reach
the network.

`NEXT_PUBLIC_API_BASE_URL` defaults to the relative path `/api`. In
production it should point at the deployed Azure Functions base URL (see
[VERCEL_DEPLOYMENT.md](VERCEL_DEPLOYMENT.md)).

## API

A single Python Azure Functions app (`api/function_app.py`, Functions v2
programming model, anonymous auth, Consumption/free plan) exposes:

- `GET /api/health`
- `GET /api/players`, `GET /api/players/{player_id}`
- `POST /api/compare`
- `POST /api/similarity`
- `POST /api/tactical-fit`
- `POST /api/scout`

Every endpoint follows the same pipeline: CORS preflight handling →
best-effort in-memory rate limiting → Pydantic request validation → business
logic in `shared/*.py` → response formatting → safe JSON error handling (no
stack traces or secrets are ever returned). See
[API_REFERENCE.md](API_REFERENCE.md) for full request/response shapes.

## Agent workflow (`/api/scout`)

`POST /api/scout` is powered by a LangGraph-inspired multi-agent workflow
implemented as plain Python functions in `shared/agent_workflow.py`: a Safety
Agent, Query Classifier, Stats Agent, SQL RAG Retriever, Similarity Agent,
Comparison Agent, Tactical Fit Agent, and Recommendation Agent. Each agent's
contribution is summarised in the response's `workflow_summary` field — the
underlying reasoning/chain-of-thought is never exposed. Full details and the
LangGraph upgrade path are in [AGENT_WORKFLOW.md](AGENT_WORKFLOW.md).

## RAG retrieval

By default, retrieval is SQL-backed keyword search over `ScoutingNotes` and
`TeamProfiles` (`shared/rag_retriever.py`) — no embeddings or vector database
required. An optional Qdrant semantic-search layer can be enabled with
`ENABLE_QDRANT=true`; if it is unavailable for any reason, retrieval silently
falls back to SQL keyword search. Details in [RAG_PROCESS.md](RAG_PROCESS.md).

## Data layer

`shared/database.py` exposes a `DataStore` interface with two
implementations:

- **`LocalSeedDataStore`** (default): loads `api/seed/sample_players.csv`,
  `sample_scouting_notes.json`, and `sample_team_profiles.json` into memory.
  Used automatically when `AZURE_SQL_CONNECTION_STRING` is unset, or as a
  fallback if any Azure SQL call raises.
- **`AzureSqlDataStore`**: uses `pyodbc` with parameterised queries only
  against the schema in `api/seed/schema.sql`.

This means the public site works immediately after deployment, even before
Azure SQL is provisioned. See [DATA_PIPELINE.md](DATA_PIPELINE.md) and
[AZURE_SQL_SETUP.md](AZURE_SQL_SETUP.md).

## LLM mode

`USE_MOCK_LLM=true` (default) generates all narrative text via deterministic
template functions in `shared/mock_llm.py` based on computed statistics — no
API key required, zero cost. Setting `ENABLE_REAL_LLM=true` with a valid
`OPENAI_API_KEY` allows an optional real LLM call to enhance narrative tone;
if that call fails or is disabled, the mock-generated text is used as a safe
fallback. Both modes produce a response in the same documented shape.

## Explainable scoring models

- **Similarity** (`shared/similarity.py`): min-max normalised, weighted
  Euclidean distance across ~14 per-90/output metrics, converted to a 0-100
  score, with the closest and most-different metrics surfaced for
  explanation.
- **Tactical fit** (`shared/tactical_fit.py`): heuristic 0-100 score
  combining pressing-intensity alignment, possession-style alignment,
  positional fit, and output metrics against a team's stated tactical
  profile and player requirements.

Both are deterministic and explainable — not machine-learning predictions.

## Optional MCP layer

`shared/mcp_tools.py` wraps the same business logic used by the public API
as plain functions (read-only: search, compare, similarity, tactical fit,
scouting report, scout query). `MCP_ENABLED=false` by default and no deployed
Azure Function calls these. See [MCP_OPTIONAL.md](MCP_OPTIONAL.md).
