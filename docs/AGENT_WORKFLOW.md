# Agent Workflow (`/api/scout`)

`POST /api/scout` runs a LangGraph-inspired multi-agent workflow implemented
as plain Python functions in `api/shared/agent_workflow.py`, orchestrated by
`run_scout_workflow(query)`.

## Why plain functions instead of LangGraph

LangGraph's runtime and dependency footprint add meaningful cold-start
weight to an Azure Functions Consumption-plan deployment, which is billed and
limited by execution time and memory. To keep the public deployment fast,
free, and dependency-light, the same node/edge structure used by a LangGraph
`StateGraph` is implemented with ordinary functions that pass a shared
`dict`-based state along. If/when a LangGraph runtime is added, each function
below maps directly onto a graph node — no logic needs to change, only the
orchestration wrapper.

## Agents (nodes)

1. **Safety Agent** (`detect_prompt_injection`, `shared/security.py`) — runs
   first, before classification. Screens the raw query for prompt-injection
   patterns (e.g. "ignore previous instructions", attempts to reveal the
   system prompt, SQL injection strings, script tags, requests for secrets).
   Matches are recorded in the response's `limitations` field — the request
   is still processed for its football content.

2. **Query Classifier** (`classify_query`) — extracts entities (player
   names, team names, positions/position groups, tactical style keywords,
   general keyword tokens) via `extract_keywords` and classifies the query
   into one of: `player_search`, `player_comparison`, `player_similarity`,
   `tactical_fit`, `scouting_report`, or `general_question`.

3. **Stats Agent** (`stats_agent`) — for `player_search` queries, parses
   constraints (age bounds from "under N"/"over N"/"young", position or
   position group, requested sort metrics like xG/assists/pressures, and an
   "undervalued"/"cheap" flag), filters the player pool, ranks by the
   relevant metric(s) — dividing by market value when "undervalued" is
   requested — and returns the top candidates.

4. **SQL RAG Retriever** (`retrieve_context`, `shared/rag_retriever.py`) —
   retrieves relevant `ScoutingNotes` and `TeamProfiles` for the matched
   players/teams/keywords. See [RAG_PROCESS.md](RAG_PROCESS.md).

5. **Similarity Agent** (`similarity_agent`, uses `shared/similarity.py`) —
   for `player_similarity` queries, identifies the reference player, applies
   any parsed constraints to the candidate pool, and computes weighted
   Euclidean similarity scores.

6. **Comparison Agent** (uses `shared/comparison.py`) — for
   `player_comparison` queries, builds a side-by-side comparison table across
   shared metrics for 2-5 matched players.

7. **Tactical Fit Agent** (uses `shared/tactical_fit.py`) — for
   `tactical_fit` queries, identifies the target team, selects candidate
   players (named players, or all players in a matched position/position
   group, or the full pool), scores each against the team's tactical profile,
   and ranks them.

8. **Recommendation Agent** — assembles the final narrative (via
   `shared/mock_llm.py` template functions, or an optional real LLM call),
   appends tactical notes where relevant, computes a `confidence_level`
   (`Low`/`Medium`/`High` based on how many players were recommended and
   whether RAG context was found), and finalises `limitations` (always
   including the "sample/demo data" disclaimer).

## Response shape

Every `/api/scout` response follows
`shared/response_formatter.assemble_scout_response()`:

```json
{
  "answer": "string - the full narrative answer",
  "recommended_players": [ /* cleaned player objects */ ],
  "supporting_statistics": [ /* compact per-player metric table */ ],
  "retrieved_context_summary": [ "string", "..." ],
  "workflow_summary": [ "string", "..." ],
  "confidence_level": "Low | Medium | High",
  "limitations": [ "string", "..." ]
}
```

`workflow_summary` is a short, human-readable list (e.g. "Query classifier
identified this as a 'player similarity' request.", "Similarity agent ranked
5 candidate(s) against Lamine Yamal."). **No hidden chain-of-thought,
intermediate prompts, or raw model reasoning is ever included** — this is an
explicit design requirement enforced by keeping all orchestration in
`agent_workflow.py` as deterministic, inspectable Python rather than free-form
LLM planning.

## Confidence levels

`_confidence_level(data_points, has_context)`:

- `Low` — no players recommended, or no players and no context.
- `Medium` — at least one player recommended.
- `High` — three or more players recommended **and** relevant RAG context was
  found.

## Logging

Each scout query is logged best-effort via `store.log_scout_query(query,
answer[:500])` — failures here never break the response (wrapped in a bare
`try/except`).

## Upgrade path to LangGraph

To swap in a real LangGraph `StateGraph`:

1. Define a `TypedDict` state mirroring the locals threaded through
   `run_scout_workflow` (`query`, `keywords`, `query_type`,
   `recommended_players`, `workflow_summary`, `limitations`, etc.).
2. Wrap each numbered function above as a node function
   `def node(state) -> state`.
3. Add conditional edges based on `query_type` (mirroring the `if/elif`
   chain in `run_scout_workflow`).
4. Keep the Safety Agent and Recommendation Agent as the entry and exit
   nodes respectively.

This is intentionally not done by default to avoid the added cold-start cost
and dependency surface on the Consumption plan.
