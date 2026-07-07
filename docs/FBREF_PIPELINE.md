# FBref Data Pipeline (Optional)

FootballQ AI ships with a small, illustrative sample dataset (~33 players,
6 clubs). This optional pipeline replaces/expands that data with real
season stats, squad stats, and match logs scraped from
[FBref](https://fbref.com), loaded into Azure SQL on a daily schedule.

**This is entirely optional.** The API and frontend work fully without it,
using the bundled sample data via `LocalSeedDataStore`. The pipeline is
disabled by default.

## Why not "real-time" / every-second updates?

Two reasons:

1. **FBref rate-limits aggressively.** Its `robots.txt` publishes a
   `Crawl-delay`, and clients that ignore it get temporarily blocked. This
   pipeline reads that directive at runtime and enforces at least
   `FBREF_REQUEST_DELAY_SECONDS` (default 6s) between every request -
   incompatible with sub-second polling.
2. **The underlying data doesn't change that fast.** FBref's stats are
   derived from completed matches. A player's season totals change at most
   a handful of times per week (after each match their team plays). A
   **daily** run is more than sufficient to stay current.

## Leagues covered

10 leagues total:

- **Big 5** (scraped together every run, via FBref's combined page):
  Premier League, La Liga, Bundesliga, Serie A, Ligue 1.
- **Extra leagues** (`pipeline/leagues.json`, rotated 1 per run by default):
  Championship (England), Eredivisie (Netherlands), Primeira Liga
  (Portugal), Brazilian Série A, Liga Profesional Argentina.

## What gets scraped

| Run step | Source page(s) | Destination table |
|---|---|---|
| Big 5 player season stats | Big 5 combined `standard`, `shooting`, `passing`, `possession`, `defense`, `gca`, `keepers`, `keepersadv`, `playingtime`, `misc` player tables | `dbo.Players` (upsert by `player_id`), `dbo.PlayerSeasonStats` (upsert by `player_id` + `season`, current season) |
| Big 5 squad stats | Big 5 combined squad `standard` stats table | `dbo.TeamStats` (upsert by `team_name` + `season`) |
| Extra league player + squad stats | Per-league `standard`/`shooting`/`passing`/`possession`/`defense`/`gca`/`keepers`/`keepersadv`/`playingtime`/`misc` + squad `standard` pages, 1 league per run (rotating, see `pipeline/leagues.json`) | `dbo.Players`, `dbo.PlayerSeasonStats`, `dbo.TeamStats` |
| Match logs | Per-team "Scores & Fixtures" pages, 1-2 teams per run (rotating) | `dbo.MatchLogs` (append-only, deduped) |

Each run also writes a row to `dbo.PipelineRuns` recording status, counts,
and which team/league to start from next time.

### Why rotate the extra leagues?

Each extra league needs its own set of 10 page fetches (no combined page like
Big5; squad stats share the `standard` page so add no extra fetch), so
scraping all 5 in one run would add ~50 fetches (~5 min at the default 6s
delay) on top of Big5 + match logs. Rotating 1 league per run
(`FBREF_EXTRA_LEAGUES_PER_RUN`, default 1) keeps a typical run to roughly
20-25 fetches (~2-3 min), comfortably inside the 10-minute Consumption
timeout, while still refreshing each extra league every ~5 days - more than
enough given these leagues' stats change at most a few times per week.

## New stat categories: goalkeeping, playing time, misc

In addition to the original `standard`/`shooting`/`passing`/`possession`/
`defense`/`gca` categories, the pipeline now also scrapes:

- **`keepers`** + **`keepersadv`** - basic and advanced goalkeeping stats
  (table ids `stats_keeper`, `stats_keeper_adv`).
- **`playingtime`** - starts, minutes per match, % of squad minutes played
  (table id `stats_playing_time`).
- **`misc`** - cards, fouls, offsides, aerial duels, recoveries (table id
  `stats_misc`).

These are scraped for every league (Big5 via `BIG5_PLAYER_STAT_PAGES`,
others via `LEAGUE_PLAYER_STAT_PAGE_TEMPLATES` in `fbref_scraper.py`) and
merged into the same per-player DataFrame as the existing categories.

`dbo.Players` (the current-season "snapshot" consumed by the live app/API)
is **not** changed - `transform_players` still only extracts the original
fields. Instead, `transform_player_season_stats` extracts all fields
(existing + new) into `dbo.PlayerSeasonStats` rows, keyed by `player_id` +
`season`. This keeps the new categories additive with zero risk to existing
API/frontend contracts.

**Out of scope**: nationalities and squad/player wages pages are not
scraped.

**FBref column mappings - verify on first run.** The new fields' FBref
source columns (`GA90`, `Save%`, `CS%`, `PSxG`, `Starts`, `Mn/MP`, `Min%`,
`CrdY`, `CrdR`, `Fls`, `Fld`, `Off`, `Won%`, `Recov` - see
`_PLAYER_GK_DIRECT_FIELDS`, `_PLAYER_PLAYING_TIME_FIELDS`,
`_PLAYER_MISC_DIRECT_FIELDS`, `_PLAYER_MISC_PER90_FIELDS` in
`pipeline/transform.py`) are based on FBref's standard column-naming scheme
but have not been verified against a live scrape. If a column is missing or
renamed, the corresponding `dbo.PlayerSeasonStats` field is simply left
`NULL` for that run - check `pipeline/transform.py` and adjust the mapping if
needed.

## `dbo.PlayerSeasonStats` and the historical backfill

`dbo.PlayerSeasonStats` holds per-season player stats (existing per-90
metrics + the new goalkeeping/playing-time/misc fields), keyed by
`(player_id, season)`. It's populated two ways:

1. **Daily pipeline** (current season only) - `run_pipeline.py` calls
   `transform_player_season_stats` for both the Big5 step and the extra-league
   step, upserting via `upsert_player_season_stats`.
2. **One-time historical backfill** - `pipeline/backfill_history.py`, a
   standalone script (NOT part of the daily Azure Function):

   ```bash
   cd api
   export AZURE_SQL_CONNECTION_STRING="<your connection string>"
   python -m pipeline.backfill_history
   ```

   Loops over all 10 leagues in `pipeline/all_leagues.json` (using each
   league's individual FBref comp id, including the 5 Big5 leagues) and the
   last 5 seasons (current season + 4 prior), scraping all 10 stat categories
   plus squad stats per league-season and upserting into
   `dbo.PlayerSeasonStats` / `dbo.TeamStats`. This is ~500 page fetches
   (~50 minutes at the default 6s crawl delay) - run it locally, once. It's
   idempotent, so it's safe to interrupt and re-run.

## `pipeline/all_leagues.json`

Lists all 10 leagues with their individual FBref comp id/slug (including the
5 Big5 leagues, scraped via the combined page for the daily pipeline but via
their individual league pages for the backfill), plus `season_format`
(`"YYYY-YYYY"` or `"YYYY"`) and `current_season`, used by
`backfill_history.py` to compute each league's last-5-seasons sequence. Only
used by the backfill script - `pipeline/leagues.json` remains the 5-entry
rotation file for the daily pipeline's extra-leagues step.

## Data size / free-tier impact

Storage is not the constraint here. Even at 10 leagues this is roughly
5,000-6,000 player rows, ~200 team rows, and match logs in the low
thousands - a few MB total, far under Azure SQL's free 32GB. The binding
constraint is FBref's rate limit and the Functions timeout, addressed by the
rotation above.

## `pipeline/leagues.json`

Lists the 5 extra leagues, each with the FBref competition id, URL slug, and
an optional `season` override for leagues that run on a calendar-year season
(Brazilian Série A, Liga Profesional Argentina use e.g. `"2026"` instead of
`"2025-2026"`):

```json
{ "league_name": "Primeira Liga", "fbref_comp_id": "32", "fbref_slug": "Primeira-Liga", "season": null }
```

All 5 comp ids/slugs (Championship `10`/`Championship`, Eredivisie
`23`/`Eredivisie`, Primeira Liga `32`/`Primeira-Liga`, Brazilian Série A
`24`/`Serie-A`, Liga Profesional Argentina `21`/`Primera-Division`) have been
verified against live FBref URLs. Add or remove leagues from this file as
needed; the pipeline rotates through however many entries it contains. Find a
league's id/slug from its FBref URL, e.g.
`https://fbref.com/en/comps/<fbref_comp_id>/<fbref_slug>-Stats`.

## New schema

`api/seed/schema.sql` adds three tables on top of the existing
`Players` / `ScoutingNotes` / `TeamProfiles`:

- **`TeamStats`** - per-season squad numbers (`matches_played`, `goals_for`,
  `goals_against`, `xg`, `xga`, `possession_pct`). Distinct from
  `TeamProfiles`, which holds curated narrative tactical-identity text used
  by the tactical-fit agent and is **not** touched by this pipeline.
- **`MatchLogs`** - one row per completed match (`result`, `goals_for/against`,
  `xg`/`xga`, `possession_pct`), for future trend/form analysis (see
  [FUTURE_IMPROVEMENTS.md](FUTURE_IMPROVEMENTS.md)).
- **`PipelineRuns`** - run history/observability and the round-robin indexes
  used to rotate which teams' match logs and which extra league get scraped
  each day.

Re-run `schema.sql` against your Azure SQL Database to add these tables
(it's idempotent - see [AZURE_SQL_SETUP.md](AZURE_SQL_SETUP.md)).

## Known data gaps

FBref doesn't publish everything `dbo.Players` has columns for:

- **`pressures_per90`** - the underlying StatsBomb defensive-pressure feed
  was discontinued for the Big 5 leagues. Left `NULL`.
- **`market_value_million`** - not published by FBref (would need
  Transfermarkt or similar - out of scope). Left `NULL`.
- **`preferred_foot`** - not present in the scraped tables. Left `NULL`.

The upsert logic uses `COALESCE(new, existing)` for these three columns, so
a daily refresh never **wipes out** values that were set another way (e.g.
the original sample data for players who are still in the dataset).

`TeamStats.goals_against` / `xga` come from FBref's separate "squads ...
against" table, which isn't scraped by default to keep each run small; they
may be `NULL` until that's added (see
[FUTURE_IMPROVEMENTS.md](FUTURE_IMPROVEMENTS.md)).

## Configuration

All settings are read by `shared/config.py`. Set these as Azure Functions
Application Settings (never commit real values):

| Variable | Default | Purpose |
|---|---|---|
| `FBREF_PIPELINE_ENABLED` | `false` | Master switch. Must be `true` to run. |
| `AZURE_SQL_CONNECTION_STRING` | _(empty)_ | Required - the pipeline writes directly to Azure SQL. |
| `FBREF_SEASON` | `2025-2026` | Default season string used for the Big 5 and any league in `leagues.json` without a `season` override; stored in `TeamStats`/`MatchLogs`. |
| `FBREF_REQUEST_DELAY_SECONDS` | `6.0` | Minimum seconds between FBref requests (raised automatically if `robots.txt` asks for more). |
| `FBREF_MATCHLOG_TEAMS_PER_RUN` | `2` | How many teams' match logs to scrape per run (rotates through `pipeline/teams.json`). |
| `FBREF_EXTRA_LEAGUES_PER_RUN` | `1` | How many non-Big5 leagues' player + squad stats to scrape per run (rotates through `pipeline/leagues.json`). |
| `FBREF_USER_AGENT` | _(descriptive default)_ | Sent with every request so FBref can identify this as a low-volume scraper. |

## Scheduling

`function_app.py` registers a timer-triggered function:

```python
@app.timer_trigger(schedule="0 0 3 * * *", arg_name="timer", run_on_startup=False, use_monitor=True)
def fbref_daily_pipeline(timer: func.TimerRequest) -> None: ...
```

This runs once daily at 03:00 UTC. It immediately returns if
`FBREF_PIPELINE_ENABLED` is not `true` or no database is configured - safe
to leave deployed even when unused.

`host.json`'s `functionTimeout` is set to `00:10:00` (the Azure Functions
Consumption plan maximum) to give the player-stats step (6 page fetches at
the configured delay) and the match-log step room to complete.

## `pipeline/teams.json`

Lists the teams eligible for match-log scraping, with their FBref squad ID
and URL slug:

```json
{ "team_name": "Barcelona", "fbref_id": "206d90db", "fbref_slug": "Barcelona" }
```

All 6 team IDs (Barcelona `206d90db`, Manchester City `b8fd03ef`, Arsenal
`18bb7c10`, Real Madrid `53a2f082`, Liverpool `822bd0ba`, Bayern Munich
`054efa67`) have been verified against live FBref squad URLs. Add or remove
teams from this file as needed; the pipeline rotates through however many
entries it contains. FBref squad IDs are an 8-character hex string visible in
a team's FBref URL, e.g.
`https://fbref.com/en/squads/<fbref_id>/<season>/<Team-Name>-Stats`.

## Running manually / locally

Requires `pip install -r api/requirements.txt` (adds `requests`, `pandas`,
`lxml`, `beautifulsoup4` on top of the base API dependencies) and
`AZURE_SQL_CONNECTION_STRING` + `FBREF_PIPELINE_ENABLED=true` set:

```bash
cd api
export FBREF_PIPELINE_ENABLED=true
export AZURE_SQL_CONNECTION_STRING="<your connection string>"
python -m pipeline.run_pipeline
```

Prints a JSON summary, e.g.:

```json
{
  "status": "success",
  "players_upserted": 2500,
  "team_stats_upserted": 98,
  "player_season_stats_upserted": 2500,
  "match_logs_inserted": 14,
  "errors": []
}
```

## Testing

`api/tests/test_pipeline_transform.py` unit-tests the FBref-table-to-schema
mapping (`pipeline/transform.py`) with small synthetic DataFrames - no
network access required, so it runs in CI like the rest of the backend
suite. The scraper (`pipeline/fbref_scraper.py`) and loader
(`pipeline/load_azure_sql.py`) are network/database-dependent and are
exercised via the manual run above.

## Cost and compliance notes

- The pipeline only runs if explicitly enabled and only writes to Azure SQL
  (already covered by the free-tier guidance in
  [COST_SAFETY.md](COST_SAFETY.md)).
- It performs a handful of GET requests per day to publicly accessible FBref
  pages, respecting `robots.txt` - well within normal personal/portfolio use.
- If FBref changes its page structure or blocks the configured User-Agent,
  the affected step is skipped (logged as an error in `PipelineRuns`) and
  the rest of the pipeline still runs; the site continues to serve whatever
  data is already in Azure SQL (or the local seed fallback).
