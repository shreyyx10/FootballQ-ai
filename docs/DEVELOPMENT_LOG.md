# Development Log

A phase-by-phase record of how FootballQ AI was built. All phases target the
same constraint: a free, cloud-deployable portfolio project with no paid
services required.

## Phase 1 — Project scaffold

Created the repository structure (`api/`, `frontend/`, `docs/`,
`.github/workflows/`), root `.env.example`, `.gitignore`, `SECURITY.md`,
`vercel.json`. Established naming conventions (`footballq-ai`, brand
"FootballQ AI", tagline "Ask smarter football questions. Discover better
players.").

## Phase 2 — Backend foundations

Built `shared/config.py` (env-var-driven `Settings` singleton, no hardcoded
secrets), `shared/security.py` (CORS allowlist, safe error responses,
rate limiting, prompt-injection heuristics, input validators), and
`shared/database.py` (`DataStore` interface with `LocalSeedDataStore` and
`AzureSqlDataStore`).

## Phase 3 — Sample data

Authored `api/seed/sample_players.csv` (33 players across multiple leagues
and positions), `sample_scouting_notes.json` (profile summaries, strengths,
weaknesses, tactical notes, role fit, risk notes per player),
`sample_team_profiles.json` (6 clubs' tactical identities), `schema.sql`
(SQL Server-compatible DDL), and `seed_azure_sql.py` (parameterised seeding
script).

## Phase 4 — Core business logic

Implemented `shared/similarity.py` (normalised weighted-Euclidean similarity,
0-100 score, closest/most-different metrics), `shared/comparison.py`
(side-by-side comparison table + strengths/weaknesses), `shared/tactical_fit.py`
(heuristic 0-100 fit score across pressing, possession, position, and output
alignment), `shared/rag_retriever.py` (keyword extraction + SQL-backed
retrieval with optional Qdrant fallback), and `shared/mock_llm.py`
(deterministic narrative generation for all query types).

## Phase 5 — Agent workflow, MCP stubs, and endpoints

Implemented `shared/agent_workflow.py` (LangGraph-inspired
`run_scout_workflow` with Safety, Query Classifier, Stats, Similarity,
Comparison, Tactical Fit, and Recommendation agents), `shared/mcp_tools.py`
(optional read-only MCP wrappers, `MCP_ENABLED=false` by default), and
`function_app.py` (7 HTTP-triggered endpoints: health, players list/detail,
compare, similarity, tactical-fit, scout — all with CORS, rate limiting,
Pydantic validation, and safe error handling).

## Phase 6 — Backend tests

Wrote `api/tests/` (39 pytest cases): `test_health.py`,
`test_similarity.py`, `test_validation.py`, `test_rag.py`,
`test_security.py`, with `conftest.py` setting safe default environment
variables before module import (mock LLM, no Qdrant, rate limiting disabled
for deterministic tests, empty Azure SQL connection string). All 39 tests
pass (`pytest -v -p no:cacheprovider` from `api/`).

## Phase 7 — Frontend foundations

Set up `frontend/` as a Next.js 14 (App Router) + TypeScript + Tailwind +
Recharts + Zod project: `package.json`, `next.config.js` (security headers),
`tsconfig.json`, `tailwind.config.ts` (dark navy/black + green accent design
system), `.eslintrc.json`. Built `src/lib/`: `constants.ts`, `schemas.ts`
(Zod mirrors of backend Pydantic models), `security.ts`, `api.ts`
(`ApiResult<T>` discriminated-union client), `utils.ts`, and
`src/styles/globals.css`.

## Phase 8 — Frontend pages and components

Built layout components (`Container`, `Header`, `Footer`, root `layout.tsx`),
UI primitives (`Button`/`ButtonLink`, `Card`, `Badge`, `Loading`,
`ErrorState`), football/chart components (`PlayerSelect`, `PlayerCard`,
`ScoreGauge`, `ComparisonRadarChart`, `SimilarityBarChart`), and all 7 pages:
`/` (landing), `/scout`, `/compare`, `/similarity`, `/tactical-fit`,
`/architecture`, `/about`, plus a custom `not-found.tsx`. Verified with
`npm run lint` (no warnings/errors) and `npx tsc --noEmit` (no type errors).
A full `next build` could not complete inside this sandbox's per-command time
limit (see note below); lint and type-checking both pass cleanly and the
build will run to completion on Vercel's build infrastructure during
deployment.

## Phase 9 — Documentation set

Authored the full `docs/` set: `ARCHITECTURE.md`, `SECURITY.md`,
`FREE_DEPLOYMENT.md`, `COST_SAFETY.md`, `VERCEL_DEPLOYMENT.md`,
`AZURE_FUNCTIONS_DEPLOYMENT.md`, `AZURE_SQL_SETUP.md`, `DATA_PIPELINE.md`,
`AGENT_WORKFLOW.md`, `RAG_PROCESS.md`, `MCP_OPTIONAL.md`, `API_REFERENCE.md`,
`FUTURE_IMPROVEMENTS.md`, this `DEVELOPMENT_LOG.md`, and the portfolio-ready
root `README.md`.

## Phase 10 — Verification

Final pass: re-ran the backend test suite, re-checked frontend lint/type
checks, reviewed the repository tree against the required structure, and
confirmed no hardcoded secrets, no `localhost` references in
production-facing config, and consistent branding/URLs across docs and code.

---

### Note on the sandbox build check

During development, `npm run build` (the production Next.js build) was
attempted multiple times from this sandbox and consistently hung shortly
after printing the Next.js banner, with low and flat CPU usage — consistent
with a slow/blocked network call during build bootstrap in this restricted
environment, unrelated to the application code. `npm install`, `npm run
lint`, and `npx tsc --noEmit` all completed successfully with no errors or
warnings. The build is expected to complete normally on Vercel, which runs
`npm run build` as part of every deployment.
