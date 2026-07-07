# Data Pipeline

FootballQ AI ships with a small, illustrative sample dataset that powers both
the in-memory fallback and the optional Azure SQL database.

## Source files (`api/seed/`)

| File | Contents |
|---|---|
| `sample_players.csv` | 33 players with `player_id`, identity fields (`player_name`, `age`, `nationality`, `club`, `league`, `position`, `preferred_foot`), playing time (`minutes`), output (`goals`, `assists`, `xg`, `xag`), per-90 metrics (`shots_per90`, `key_passes_per90`, `progressive_passes_per90`, `progressive_carries_per90`, `successful_takeons_per90`, `shot_creating_actions_per90`, `tackles_per90`, `interceptions_per90`, `pressures_per90`, `pass_completion_pct`), and `market_value_million`. |
| `sample_scouting_notes.json` | 33 records keyed by `player_id` with `profile_summary`, `strengths`, `weaknesses`, `tactical_notes`, `role_fit`, and `risk_notes` — free text used by the SQL-backed RAG retriever. |
| `sample_team_profiles.json` | 6 club tactical profiles with `team_name`, `tactical_style`, `formation`, `pressing_intensity`, `possession_style`, and `player_requirements` — used by the Tactical Fit Agent and RAG retriever. |
| `schema.sql` | SQL Server-compatible DDL for `Players`, `ScoutingNotes`, `TeamProfiles`, `ScoutQueries`, `ApiLogs`, plus indexes. Idempotent (drops tables before recreating). |
| `seed_azure_sql.py` | Reads the three sample files above and inserts them into Azure SQL using parameterised `pyodbc` queries. Safe to re-run. |

## Two data stores, one interface

`api/shared/database.py` defines a `DataStore` interface
(`get_players`, `get_player`, `get_team_profiles`, `get_team_profile`,
`get_scouting_notes`, `search_scouting_notes`, `search_team_profiles`,
`log_api_call`, `log_scout_query`) with two implementations:

- **`LocalSeedDataStore`** — loads the three sample files into memory at
  process start. Used whenever `AZURE_SQL_CONNECTION_STRING` is empty, and
  as an automatic fallback if any `AzureSqlDataStore` call raises.
- **`AzureSqlDataStore`** — runs the equivalent queries against Azure SQL
  using parameterised statements only.

`get_data_store()` returns whichever is configured, so `function_app.py` and
`shared/agent_workflow.py` never need to know which backend is active.

## Why this design

- **Zero-config demo**: the public site works the moment it's deployed,
  before any database is provisioned.
- **Graceful degradation**: if Azure SQL is paused, misconfigured, or
  unreachable, requests still succeed using the same sample data — users
  never see a 500 caused purely by a database issue.
- **Single source of truth**: both stores are seeded from (or equivalent to)
  the same three files, so results are consistent regardless of which store
  is active.

## Updating or extending the dataset

To add players, teams, or scouting notes:

1. Edit `sample_players.csv` / `sample_scouting_notes.json` /
   `sample_team_profiles.json`, keeping `player_id` consistent across files
   (format `pNNN`) and `team_name` consistent between `sample_team_profiles.json`
   and any references in `sample_scouting_notes.json`.
2. If using Azure SQL, re-run `python seed_azure_sql.py` (it clears and
   re-inserts).
3. The in-memory store picks up changes to the JSON/CSV files automatically
   on the next process start (no code changes needed).
4. Run `pytest` from `api/` — `test_similarity.py` and `test_rag.py` assert
   a minimum player count and basic shape, so additions should not break
   them, but large schema changes should be reflected in `schema.sql` and
   `shared/schemas.py` as well.

## Data provenance and disclaimer

The sample dataset reflects real, well-known players' approximate
historical statistics for illustrative purposes. It is a small, static
snapshot — not a live feed — and `/api/scout` responses always include a
limitation noting the data is for demo purposes only.
