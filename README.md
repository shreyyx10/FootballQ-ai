# FootballQ AI

**Ask smarter football questions. Discover better players.**

FootballQ AI is a multi-agent football scouting assistant: ask natural-language
questions, compare players, find statistically similar profiles, and assess
tactical fit against a club's playing style — all powered by a transparent,
explainable agent workflow and deployable entirely on free-tier cloud
services.

Live demo: **https://footballq-ai.vercel.app**

> Built as a portfolio project. The dataset is a small sample for
> illustration and should not be used for real scouting or transfer
> decisions. See [docs/SECURITY.md](docs/SECURITY.md) for security notes —
> this project is built with security-conscious controls for a public demo
> and is **not** claimed to be unhackable.

## What it does

| Page | What it does |
|---|---|
| `/` | Landing page introducing FootballQ AI |
| `/scout` | "Q Scout" — ask a natural-language scouting question and get a structured, multi-agent answer |
| `/compare` | Side-by-side statistical comparison of 2-5 players |
| `/similarity` | Find players statistically similar to a reference player, with an explainable 0-100 score |
| `/tactical-fit` | Assess how well a player's profile fits a club's tactical identity, with an explainable 0-100 score |
| `/architecture` | How the system is built, end to end |
| `/about` | Project background, security controls, and known limitations |

## Tech stack

- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS, Recharts,
  Zod — deployed on **Vercel Hobby**.
- **API**: Python Azure Functions (Consumption/free plan), Pydantic
  validation, CORS allowlist, rate limiting.
- **Data**: Azure SQL Database (free offer), SQL Server-compatible schema,
  parameterised queries — with a zero-config in-memory fallback seeded from
  the same sample data.
- **AI**: Mock-LLM mode by default (deterministic, zero-cost narratives);
  optional real LLM via `OPENAI_API_KEY` (disabled by default). SQL-backed
  RAG retrieval by default; optional Qdrant semantic layer.
- **Agents**: A LangGraph-inspired multi-agent workflow (Safety, Query
  Classifier, Stats, SQL RAG Retriever, Similarity, Comparison, Tactical Fit,
  Recommendation) implemented as plain Python functions.

## Repository structure

```
footballq-ai/
├── README.md
├── .env.example
├── .gitignore
├── SECURITY.md
├── vercel.json
├── .github/workflows/
│   ├── ci.yml                  # pytest (backend) + lint/build (frontend)
│   └── security-checks.yml     # dependency audits + secret scan
├── docs/                        # full documentation set (see below)
├── api/                          # Azure Functions (Python)
│   ├── function_app.py
│   ├── host.json
│   ├── requirements.txt
│   ├── shared/                  # config, security, database, agents, scoring
│   ├── pipeline/                # optional daily FBref data pipeline (see docs/FBREF_PIPELINE.md)
│   ├── seed/                    # sample data, schema.sql, seed script
│   └── tests/                   # pytest suite
└── frontend/                     # Next.js 14 app
    ├── src/app/                  # pages: /, /scout, /compare, /similarity, /tactical-fit, /architecture, /about
    ├── src/components/           # layout, ui, football, charts
    └── src/lib/                  # api client, zod schemas, constants, utils
```

## Documentation

| Doc | Covers |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design end to end |
| [docs/AGENT_WORKFLOW.md](docs/AGENT_WORKFLOW.md) | The 8-agent `/api/scout` workflow and LangGraph upgrade path |
| [docs/RAG_PROCESS.md](docs/RAG_PROCESS.md) | SQL-backed retrieval, optional Qdrant |
| [docs/API_REFERENCE.md](docs/API_REFERENCE.md) | Every endpoint, request/response shapes, `curl` examples |
| [docs/DATA_PIPELINE.md](docs/DATA_PIPELINE.md) | Sample data, schema, local-seed fallback |
| [docs/MCP_OPTIONAL.md](docs/MCP_OPTIONAL.md) | Optional MCP tool stubs |
| [docs/SECURITY.md](docs/SECURITY.md) | Implemented controls and known limitations |
| [docs/FREE_DEPLOYMENT.md](docs/FREE_DEPLOYMENT.md) | Deployment overview and order of operations |
| [docs/VERCEL_DEPLOYMENT.md](docs/VERCEL_DEPLOYMENT.md) | Deploying the frontend |
| [docs/AZURE_FUNCTIONS_DEPLOYMENT.md](docs/AZURE_FUNCTIONS_DEPLOYMENT.md) | Deploying the API |
| [docs/AZURE_SQL_SETUP.md](docs/AZURE_SQL_SETUP.md) | Optional database setup and seeding |
| [docs/FBREF_PIPELINE.md](docs/FBREF_PIPELINE.md) | Optional daily FBref data pipeline (real player/team/match stats) |
| [docs/COST_SAFETY.md](docs/COST_SAFETY.md) | Why this stays free, and how to keep it that way |
| [docs/DEVELOPMENT_LOG.md](docs/DEVELOPMENT_LOG.md) | Phase-by-phase build log |
| [docs/FUTURE_IMPROVEMENTS.md](docs/FUTURE_IMPROVEMENTS.md) | Ideas for extending the project |

## Quick start (local development)

```bash
# Backend
cd api
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install pytest
pytest -v                # 39 tests, all using mock LLM + local seed data
func start                # requires Azure Functions Core Tools v4

# Frontend (separate terminal)
cd frontend
npm install
npm run lint
npx tsc --noEmit
npm run dev               # set NEXT_PUBLIC_API_BASE_URL=http://localhost:7071/api in .env.local
```

## Deployment (free tier)

1. **API → Azure Functions** (Consumption/free plan) — see
   [docs/AZURE_FUNCTIONS_DEPLOYMENT.md](docs/AZURE_FUNCTIONS_DEPLOYMENT.md).
   Works out of the box with mock LLM and local seed data.
2. **Frontend → Vercel** (Hobby plan) — see
   [docs/VERCEL_DEPLOYMENT.md](docs/VERCEL_DEPLOYMENT.md). Set
   `NEXT_PUBLIC_API_BASE_URL` to the Function App's URL.
3. **(Optional) Azure SQL** — see
   [docs/AZURE_SQL_SETUP.md](docs/AZURE_SQL_SETUP.md) to provision the free
   database and run `api/seed/seed_azure_sql.py`.

Full walkthrough: [docs/FREE_DEPLOYMENT.md](docs/FREE_DEPLOYMENT.md).

## Environment variables

See [.env.example](.env.example) for the full list. Defaults are
safe/free-cost: `USE_MOCK_LLM=true`, `ENABLE_REAL_LLM=false`,
`ENABLE_QDRANT=false`, `MCP_ENABLED=false`, `RATE_LIMIT_ENABLED=true`.
`AZURE_SQL_CONNECTION_STRING`, `OPENAI_API_KEY`, and `QDRANT_API_KEY` are
never committed — configure them only as Azure Functions Application
Settings / Vercel environment variables if you choose to enable those
features.

## Testing

- **Backend**: `pytest -v` from `api/` (39 tests covering health, players,
  similarity, validation, RAG retrieval, and prompt-injection handling).
- **Frontend**: `npm run lint` and `npx tsc --noEmit` from `frontend/` (both
  pass with no warnings or errors); `npm run build` runs as part of every
  Vercel deployment.
- **CI**: `.github/workflows/ci.yml` runs both suites on every push/PR to
  `main`; `.github/workflows/security-checks.yml` runs dependency audits and
  a basic committed-secret scan.

## Security and cost

- Security model and controls: [docs/SECURITY.md](docs/SECURITY.md) and
  [SECURITY.md](SECURITY.md).
- Cost controls and free-tier guardrails: [docs/COST_SAFETY.md](docs/COST_SAFETY.md).

## Known limitations

- The dataset (~33 players, 6 clubs) is a small, illustrative sample, not a
  comprehensive or live scouting database.
- Mock-LLM mode produces template-based narratives; tone may change with a
  real LLM enabled, but the underlying statistics do not.
- Similarity and tactical-fit scores are heuristic and explainable, not
  machine-learning predictions.
- Rate limiting is in-memory and per-instance — a best-effort guard, not an
  API gateway.

See [docs/FUTURE_IMPROVEMENTS.md](docs/FUTURE_IMPROVEMENTS.md) for where this
could go next.
