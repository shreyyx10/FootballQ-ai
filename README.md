# FootballQ AI

**Ask smarter football questions. Discover better players.**

FootballQ AI is a multi-agent football scouting assistant: ask natural-language
questions, compare players, find statistically similar profiles, and assess
tactical fit against a club's playing style — powered by a transparent,
explainable agent workflow, fed by a fully automated data pipeline covering
**10 leagues, ~3,400 players, and 5 seasons of history**, and running entirely
on free-tier infrastructure at **$0/month**.

> Built as a portfolio project. Not intended for real scouting or transfer
> decisions. See [docs/SECURITY.md](docs/SECURITY.md) for the security model —
> security-conscious for a public demo, not claimed to be unhackable.

---

## What it does

| Page | What it does |
|---|---|
| `/` | Landing page introducing FootballQ AI |
| `/scout` | "Q Scout" — ask a natural-language scouting question and get a structured, multi-agent answer |
| `/compare` | Side-by-side statistical comparison of 2–5 players |
| `/similarity` | Find players statistically similar to a reference player, with an explainable 0–100 score |
| `/tactical-fit` | Assess how well a player's profile fits a club's tactical identity, with an explainable 0–100 score |
| `/architecture` | How the system is built, end to end |
| `/about` | Project background, security controls, and known limitations |

## Architecture

```
                        ┌────────────────────────────────────────────┐
                        │        GitHub Actions (free cron)          │
                        │  daily 05:30 UTC · manual backfill/health  │
                        └─────────────────────┬──────────────────────┘
                                              │  python -m pipeline.run_pipeline
                                              ▼
   ┌──────────────┐  Save Page Now   ┌─────────────────┐   snapshots   ┌───────────────────┐
   │   FBref.com  │ ◄─────────────── │ Wayback Machine │ ─────────────►│  fbref_scraper.py │
   │ (stats source)│    captures     │ (web.archive.org)│   (raw HTML)  │ parse + rate-limit │
   └──────────────┘                  └─────────────────┘               └─────────┬─────────┘
                                                                                 │ DataFrames
                                                                                 ▼
                                                                       ┌───────────────────┐
                                                                       │   transform.py    │
                                                                       │ FBref → schema rows│
                                                                       └─────────┬─────────┘
                                                                                 │ upserts (ON CONFLICT)
                                                                                 ▼
   ┌──────────────┐    HTTPS/JSON    ┌─────────────────┐   psycopg     ┌───────────────────┐
   │   Next.js 14 │ ◄──────────────► │  Python API     │ ◄────────────►│  PostgreSQL       │
   │ (Vercel free)│                  │ (Azure Functions │               │ (Neon free tier)  │
   └──────────────┘                  │  runtime, local) │               └───────────────────┘
                                     └─────────────────┘
```

Three independent layers, each replaceable:

1. **Data pipeline** — scheduled GitHub Actions job that scrapes FBref
   statistics (via the Wayback Machine — see below), transforms them to the
   schema, and upserts into Postgres. Idempotent, resumable, observable.
2. **API** — Python endpoints (Pydantic validation, CORS allowlist, rate
   limiting) exposing players, comparison, similarity, tactical fit, and the
   multi-agent `/scout` workflow. Falls back to bundled sample data when no
   database is configured, so the demo always works.
3. **Frontend** — Next.js 14 (App Router) on Vercel's free Hobby tier.

## The data pipeline (the interesting part)

**Coverage:** 10 leagues — Premier League, La Liga, Bundesliga, Serie A,
Ligue 1 (scraped via FBref's combined Big-5 pages), plus Championship,
Eredivisie, Primeira Liga, Brazilian Série A, and Liga Profesional Argentina
(rotated one per day). 10 stat categories per player: standard, shooting,
passing, possession, defense, goal-creating actions, goalkeeping (basic +
advanced), playing time, and miscellaneous. Squad-level stats and per-match
logs on top.

**Why the Wayback Machine?** FBref blocks all non-browser HTTP clients
(Cloudflare returns 403 regardless of User-Agent, based on TLS
fingerprinting). Rather than circumvent that with browser impersonation or
rotating proxies — which would violate the site's terms and is deliberately
avoided here — the pipeline reads FBref pages from **Internet Archive
snapshots**:

1. Look up the page's most recent snapshot (Wayback availability API).
2. If it's fresh (≤ 2 days, configurable), fetch it — the raw original HTML,
   so the existing parser works unchanged.
3. If stale or missing, trigger a **Save Page Now** capture (the Archive's
   crawler can reach FBref) and use the fresh snapshot.
4. If the capture fails (quota/outage), gracefully fall back to the stale
   snapshot; if there's none, skip that table and continue.

Data lags the live site by up to ~2 days, which is a non-issue for
season-cumulative statistics. Every request is rate-limited (6 s between
requests, 15 s minimum between Save Page Now captures) out of politeness to
the Archive.

**Resilience details:**

- All upserts are `INSERT … ON CONFLICT DO UPDATE` — every job is idempotent
  and safe to interrupt/re-run, including the 10-league × 5-season historical
  backfill.
- The DB connection wrapper transparently reconnects — Neon's free tier
  closes idle connections during long scraping gaps between writes.
- Curated fields (e.g. `market_value_million`) are `COALESCE`-preserved so a
  daily refresh never overwrites them with NULLs.
- Every run writes a `PipelineRuns` row (status, row counts, error summary,
  rotation state), and `python -m pipeline.health_check` prints a full
  data-layer health report. A run that upserts zero rows is recorded as
  `partial`, never `success`.
- Match-log teams and extra leagues rotate across runs via indexes stored in
  `PipelineRuns`, keeping each run small.

## Tech stack

- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS, Recharts,
  Zod — deployed on **Vercel Hobby** (free).
- **API**: Python, Pydantic validation, CORS allowlist, rate limiting
  (Azure Functions programming model; runs locally with Core Tools).
- **Database**: **PostgreSQL on Neon free tier** (no card required), psycopg 3,
  parameterised queries only, `ON CONFLICT` upserts — with a zero-config
  in-memory fallback seeded from bundled sample data.
- **Data pipeline**: Python (`requests` + `pandas.read_html` + lxml/html5lib),
  Wayback Machine fetch strategy, scheduled by **GitHub Actions** (free).
- **AI**: Real-LLM narratives via any OpenAI-compatible endpoint — runs
  **locally on Ollama** for $0 (`LLM_BASE_URL=http://localhost:11434/v1`), or
  against OpenAI with a key. Always grounded in the structured statistics,
  with deterministic template fallback if the LLM is unavailable. SQL-backed
  RAG retrieval by default; optional Qdrant semantic layer.
- **Agents**: A **LangGraph `StateGraph`** multi-agent workflow — Safety,
  Query Classifier, and a conditional edge routing to specialist agents
  (Stats, Comparison, Similarity, Tactical Fit, Scouting Report), converging
  on a Recommendation/finalize node that composes the LLM narrative. Degrades
  to a sequential executor if langgraph isn't installed.
- **CI**: pytest + frontend lint/typecheck on every push; dependency audits
  and secret scanning.

## Data model

| Table | Keyed by | Holds |
|---|---|---|
| `Players` | `player_id` | Current-season snapshot: per-90 metrics, xG/xAG, market value, position |
| `PlayerSeasonStats` | `player_id + season` | Per-season history incl. goalkeeping, playing-time, and misc categories (5 seasons × 10 leagues) |
| `TeamStats` | `team_name + season` | Squad-level totals: xG, xGA, possession, goals for/against |
| `MatchLogs` | `team + season + date + opponent` | Per-match results with xG (append-only) |
| `ScoutingNotes`, `TeamProfiles` | — | Curated text used by the RAG retriever and tactical-fit agent |
| `PipelineRuns` | `run_id` | Pipeline observability + rotation state |
| `ScoutQueries`, `ApiLogs` | — | Request logging |

## Repository structure

```
footballq-ai/
├── README.md
├── .github/workflows/
│   ├── fbref-pipeline.yml     # daily data pipeline + manual schema/seed/backfill/health jobs
│   ├── ci.yml                 # pytest (backend) + lint/build (frontend)
│   └── security-checks.yml    # dependency audits + secret scan
├── docs/                      # full documentation set (see below)
├── api/
│   ├── function_app.py        # API endpoints
│   ├── requirements.txt
│   ├── shared/                # config, security, database (Postgres + local fallback), agents, scoring
│   ├── pipeline/
│   │   ├── fbref_scraper.py   # Wayback-based fetch + FBref table parsing + rate limiting
│   │   ├── transform.py       # FBref DataFrames → schema rows
│   │   ├── load_azure_sql.py  # psycopg upsert helpers (name is historical)
│   │   ├── run_pipeline.py    # daily orchestrator
│   │   ├── backfill_history.py# one-time 10-league × 5-season backfill
│   │   ├── health_check.py    # data-layer health report
│   │   └── *.json             # league/team configuration
│   ├── seed/                  # schema.sql (Postgres), apply_schema.py, sample data, seed script
│   └── tests/                 # pytest suite (60 tests)
└── frontend/                  # Next.js 14 app
    ├── src/app/               # /, /scout, /compare, /similarity, /tactical-fit, /architecture, /about
    ├── src/components/        # layout, ui, football, charts
    └── src/lib/               # api client, zod schemas, constants, utils
```

## Quick start (local)

**Backend + tests (no database needed):**

```bash
cd api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest
pytest -q                 # 60 tests, all offline (mock LLM + local seed data)
```

**Database + real data (free, ~15 min):**

```bash
# 1. Create a free Postgres at https://neon.tech (no card), copy the connection string
export DATABASE_URL="postgresql://…"

# 2. Create tables and load sample data
python -m seed.apply_schema
python -m seed.seed_azure_sql

# 3. Run the pipeline once (10–30 min first time; Archive captures are slow)
export FBREF_PIPELINE_ENABLED=true
python -m pipeline.run_pipeline

# 4. Verify
python -m pipeline.health_check
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev               # set NEXT_PUBLIC_API_BASE_URL in .env.local
```

## Automated pipeline setup (GitHub Actions)

1. Add your Neon connection string as the repository secret **`DATABASE_URL`**
   (Settings → Secrets and variables → Actions).
2. Actions tab → **FBref pipeline** → *Run workflow*:
   - `job=schema` (once — creates tables, **wipes existing data**)
   - `job=seed` (once — sample players/notes/profiles)
   - `job=backfill` (historical seasons; slow, resumable — re-run until
     `job=health` shows 10 leagues × 5 seasons)
3. Done. The daily 05:30 UTC schedule keeps current-season data fresh.

## Environment variables

Safe/free defaults throughout; see [.env.example](.env.example) for the full list.

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | — | Postgres connection string (falls back to in-memory sample data if unset) |
| `FBREF_PIPELINE_ENABLED` | `false` | Master switch for the data pipeline |
| `FBREF_FETCH_MODE` | `wayback` | `wayback` (Archive snapshots) or `direct` (blocked by FBref as of 2026) |
| `FBREF_WAYBACK_MAX_SNAPSHOT_AGE_DAYS` | `2` | Snapshot freshness threshold before requesting a new capture |
| `FBREF_REQUEST_DELAY_SECONDS` | `6` | Minimum delay between HTTP requests |
| `USE_MOCK_LLM` / `ENABLE_REAL_LLM` | `true` / `false` | Deterministic narratives vs. real LLM (`OPENAI_API_KEY`) |
| `ENABLE_QDRANT` | `false` | Optional semantic-search layer |
| `RATE_LIMIT_ENABLED` | `true` | API rate limiting |

## Documentation

| Doc | Covers |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System design end to end |
| [docs/AGENT_WORKFLOW.md](docs/AGENT_WORKFLOW.md) | The 8-agent `/api/scout` workflow and LangGraph upgrade path |
| [docs/RAG_PROCESS.md](docs/RAG_PROCESS.md) | SQL-backed retrieval, optional Qdrant |
| [docs/API_REFERENCE.md](docs/API_REFERENCE.md) | Every endpoint, request/response shapes, `curl` examples |
| [docs/FBREF_PIPELINE.md](docs/FBREF_PIPELINE.md) | The FBref data pipeline in depth |
| [docs/APIFY_EVALUATION.md](docs/APIFY_EVALUATION.md) | Why third-party scraping actors were evaluated and rejected |
| [docs/DATA_PIPELINE.md](docs/DATA_PIPELINE.md) | Sample data, schema, local-seed fallback |
| [docs/SECURITY.md](docs/SECURITY.md) | Implemented controls and known limitations |
| [docs/COST_SAFETY.md](docs/COST_SAFETY.md) | Why this stays free, and how to keep it that way |
| [docs/DEVELOPMENT_LOG.md](docs/DEVELOPMENT_LOG.md) | Phase-by-phase build log |
| [docs/FUTURE_IMPROVEMENTS.md](docs/FUTURE_IMPROVEMENTS.md) | Ideas for extending the project |

## Testing

- **Backend**: `pytest -q` from `api/` — 60 tests covering health, players,
  similarity, validation, RAG retrieval, pipeline transforms, and
  prompt-injection handling. All offline.
- **Frontend**: `npm run lint` and `npx tsc --noEmit` from `frontend/`.
- **CI**: both suites run on every push/PR; separate workflow for dependency
  audits and secret scanning.

## Cost

$0/month by design: Neon free tier (Postgres), GitHub Actions free tier
(pipeline cron + CI), Vercel Hobby (frontend), Internet Archive (data
access), mock-LLM mode (no API fees). Guardrails documented in
[docs/COST_SAFETY.md](docs/COST_SAFETY.md).

## Known limitations

- Pipeline data freshness is bounded by Wayback snapshot age (typically ≤ 2
  days behind FBref) — irrelevant for season-cumulative stats, unsuitable for
  live-match use cases.
- Mock-LLM mode produces template-based narratives; tone changes with a real
  LLM enabled, the underlying statistics do not.
- Similarity and tactical-fit scores are explainable heuristics, not
  machine-learning predictions.
- Rate limiting is in-memory and per-instance — a best-effort guard, not an
  API gateway.

See [docs/FUTURE_IMPROVEMENTS.md](docs/FUTURE_IMPROVEMENTS.md) for the roadmap.
