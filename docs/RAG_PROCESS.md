# RAG (Retrieval-Augmented Generation) Process

FootballQ AI's retrieval layer (`api/shared/rag_retriever.py`) is **SQL-backed
by default and requires no paid embeddings or vector database.**

## Default: SQL keyword retrieval

`retrieve_context(query, reference_player_ids=None)` works in three steps:

1. **`extract_keywords(query, players, team_profiles)`** scans the raw query
   text for:
   - **Player names** — full name or last name (if >3 characters) appears in
     the query.
   - **Team names** — exact (case-insensitive) match against
     `TeamProfiles.team_name`.
   - **Positions** — exact or pluralised match against distinct `position`
     values in the player dataset.
   - **Position groups** — generic terms like "midfielders", "wingers",
     "strikers", "full-backs", "centre-backs"/"defenders" map to a fragment
     (e.g. `"Midfielder"`) matched against any position containing it.
   - **Tactical style keywords** — a fixed list (possession, pressing,
     counter-attack, high line, low block, tiki-taka, direct, vertical,
     overlap, inverted, wing-back, build-up, tempo, etc.).
   - **General keywords** — remaining alphabetic tokens, with a stopword list
     (articles, generic football/query words) removed, used as a fallback
     search.

2. **Scouting note retrieval**: any explicitly matched player IDs (from the
   caller or from matched names) fetch their `ScoutingNotes` directly via
   `store.get_scouting_notes(ids)`. The result is supplemented with
   `store.search_scouting_notes(search_terms, limit=5)` — a weighted keyword
   search over player names, positions, and general keyword tokens — capped
   at 5 notes total, de-duplicated by `player_id`.

3. **Team profile retrieval**: if a team was named explicitly, its profile is
   fetched directly. Otherwise, if style or general keywords were found,
   `store.search_team_profiles(...)` returns up to 2 profiles ranked by
   keyword match against `tactical_style`, `possession_style`, and
   `player_requirements`.

The function returns:

```python
{
  "scouting_notes": [...],
  "team_profiles": [...],
  "retrieved_context_summary": ["Scouting note retrieved for ...", "Team profile retrieved for ... (4-3-3, Possession-heavy ...)"],
  "method": "sql_keyword",  # or "qdrant"
  "keywords": {...},
}
```

If nothing matches, `retrieved_context_summary` is
`["No closely matching scouting notes or team profiles found - using player
statistics only."]` — the workflow still proceeds using player statistics
alone.

## Optional: Qdrant semantic search

Setting `ENABLE_QDRANT=true` and `QDRANT_URL` activates
`_qdrant_search(query)`, which:

- Initialises a `QdrantClient` with a 5-second timeout.
- Is currently a placeholder — no embedding model is configured by default,
  so it logs that semantic search is not configured and returns `None`,
  causing the caller to use SQL retrieval (`method: "sql_keyword"`).
- **Never raises.** Any exception (missing dependency, network error,
  misconfiguration) is caught and logged at `warning` level, and the
  function returns `None` so retrieval falls back to SQL keyword search.

To make this fully functional, a future implementation would:

1. Choose a free/low-cost embedding provider (or a local embedding model).
2. Pre-populate a Qdrant collection from `ScoutingNotes`/`TeamProfiles`
   (e.g. via a one-off script in `api/seed/`).
3. Embed the incoming query and search the collection, returning matches in
   the same shape as the SQL path so `agent_workflow.py` requires no changes.

## Why SQL keyword search is the default

- **Zero additional cost or infrastructure** — works against the same
  `LocalSeedDataStore` / `AzureSqlDataStore` already used for everything
  else.
- **Deterministic and explainable** — every retrieved note/profile can be
  traced to a specific keyword match, which keeps `workflow_summary`
  meaningful and avoids "black box" retrieval in a free public demo.
- **Good enough for a small, curated dataset** — with ~33 players and 6
  teams, keyword matching on names, positions, and tactical terms covers the
  vast majority of realistic scouting queries.
