"""
PostgreSQL load helpers for the FBref data pipeline.

(Module name is historical - this originally targeted Azure SQL via pyodbc.
The project moved to free-tier PostgreSQL (Neon/Supabase) + psycopg; see
docs/APIFY_EVALUATION.md and docs/FBREF_PIPELINE.md.)

All queries use `%s` parameter placeholders only (psycopg), following the
same convention as `shared/database.py` and `seed/seed_azure_sql.py`. No
user input ever reaches these functions - all values originate from FBref's
public stat pages via `fbref_scraper` + `transform`.

Upsert strategy:
- `Players` is upserted by `player_id` using INSERT .. ON CONFLICT DO
  UPDATE. Fields the FBref pipeline cannot populate (`pressures_per90`,
  `market_value_million`, `preferred_foot`) use COALESCE(new, existing) so
  a daily refresh never wipes out curated values (e.g. from the original
  sample dataset) with NULLs.
- `TeamStats` is upserted by `(team_name, season)`.
- `PlayerSeasonStats` is upserted by `(player_id, season)`.
- `MatchLogs` is append-only per `(team_name, season, match_date,
  opponent)` - ON CONFLICT DO NOTHING (matches are immutable once played).
- `PipelineRuns` tracks run status and the round-robin indexes used to
  rotate match-log teams and extra leagues across runs.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("footballq.pipeline.load_db")


class ReconnectingConnection:
    """psycopg connection wrapper that transparently reconnects.

    Neon/Supabase free tiers close connections that sit idle, and pipeline
    runs spend many minutes scraping between database writes - so the
    connection is routinely dead by the next upsert batch. `cursor()`
    performs a cheap liveness check (SELECT 1) and reconnects if needed.
    """

    def __init__(self, connection_string: str):
        self._connection_string = connection_string
        self._conn = None
        self._connect()

    def _connect(self) -> None:
        import psycopg  # imported lazily, same pattern as shared/database.py

        self._conn = psycopg.connect(self._connection_string, connect_timeout=30)

    def cursor(self):
        import psycopg

        if self._conn is None or self._conn.closed:
            logger.info("Database connection closed; reconnecting")
            self._connect()
        else:
            try:
                self._conn.execute("SELECT 1")
            except psycopg.Error:
                logger.info("Database connection dead; reconnecting")
                self._connect()
        return self._conn.cursor()

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        if self._conn is not None and not self._conn.closed:
            self._conn.close()


def get_connection(connection_string: str):
    return ReconnectingConnection(connection_string)


_PLAYERS_COLUMNS = [
    "player_id", "player_name", "age", "nationality", "club", "league", "position",
    "minutes", "goals", "assists", "xg", "xag", "shots_per90", "key_passes_per90",
    "progressive_passes_per90", "progressive_carries_per90", "successful_takeons_per90",
    "shot_creating_actions_per90", "tackles_per90", "interceptions_per90",
    "pressures_per90", "pass_completion_pct", "market_value_million", "preferred_foot",
]

# Columns where a NULL from the pipeline should NOT overwrite an existing value.
_PRESERVE_EXISTING_IF_NULL = {"pressures_per90", "market_value_million", "preferred_foot"}

_PLAYERS_UPSERT_SQL = f"""
INSERT INTO Players ({", ".join(_PLAYERS_COLUMNS)})
VALUES ({", ".join("%s" for _ in _PLAYERS_COLUMNS)})
ON CONFLICT (player_id) DO UPDATE SET
{", ".join(
    f"{c} = COALESCE(EXCLUDED.{c}, Players.{c})" if c in _PRESERVE_EXISTING_IF_NULL
    else f"{c} = EXCLUDED.{c}"
    for c in _PLAYERS_COLUMNS if c != "player_id"
)}
"""


def upsert_players(conn, players: list[dict[str, Any]]) -> int:
    if not players:
        return 0
    cursor = conn.cursor()
    for player in players:
        params = [player.get(col) for col in _PLAYERS_COLUMNS]
        cursor.execute(_PLAYERS_UPSERT_SQL, params)
    conn.commit()
    return len(players)


_TEAM_STATS_COLUMNS = [
    "team_name", "league", "season", "matches_played", "goals_for",
    "goals_against", "xg", "xga", "possession_pct",
]

_TEAM_STATS_UPSERT_SQL = f"""
INSERT INTO TeamStats ({", ".join(_TEAM_STATS_COLUMNS)})
VALUES ({", ".join("%s" for _ in _TEAM_STATS_COLUMNS)})
ON CONFLICT (team_name, season) DO UPDATE SET
{", ".join(f"{c} = EXCLUDED.{c}" for c in _TEAM_STATS_COLUMNS if c not in ("team_name", "season"))},
updated_at = now()
"""


def upsert_team_stats(conn, team_rows: list[dict[str, Any]]) -> int:
    if not team_rows:
        return 0
    cursor = conn.cursor()
    for row in team_rows:
        params = [row.get(col) for col in _TEAM_STATS_COLUMNS]
        cursor.execute(_TEAM_STATS_UPSERT_SQL, params)
    conn.commit()
    return len(team_rows)


_PLAYER_SEASON_STATS_COLUMNS = [
    "player_id", "player_name", "season", "league", "club", "position", "nationality", "age",
    "minutes", "goals", "assists", "xg", "xag", "shots_per90", "key_passes_per90",
    "progressive_passes_per90", "progressive_carries_per90", "successful_takeons_per90",
    "shot_creating_actions_per90", "tackles_per90", "interceptions_per90", "pass_completion_pct",
    "gk_goals_against_per90", "gk_save_pct", "gk_clean_sheet_pct", "gk_psxg",
    "starts", "minutes_per_match", "minutes_pct",
    "yellow_cards", "red_cards", "fouls_committed_per90", "fouls_drawn_per90",
    "offsides_per90", "aerials_won_pct", "ball_recoveries_per90",
]

_PLAYER_SEASON_STATS_UPSERT_SQL = f"""
INSERT INTO PlayerSeasonStats ({", ".join(_PLAYER_SEASON_STATS_COLUMNS)})
VALUES ({", ".join("%s" for _ in _PLAYER_SEASON_STATS_COLUMNS)})
ON CONFLICT (player_id, season) DO UPDATE SET
{", ".join(f"{c} = EXCLUDED.{c}" for c in _PLAYER_SEASON_STATS_COLUMNS if c not in ("player_id", "season"))},
updated_at = now()
"""


def upsert_player_season_stats(conn, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    cursor = conn.cursor()
    for row in rows:
        params = [row.get(col) for col in _PLAYER_SEASON_STATS_COLUMNS]
        cursor.execute(_PLAYER_SEASON_STATS_UPSERT_SQL, params)
    conn.commit()
    return len(rows)


_MATCH_LOG_COLUMNS = [
    "team_name", "season", "match_date", "competition", "venue", "opponent",
    "result", "goals_for", "goals_against", "xg", "xga", "possession_pct",
]

_MATCH_LOG_INSERT_SQL = f"""
INSERT INTO MatchLogs ({", ".join(_MATCH_LOG_COLUMNS)})
VALUES ({", ".join("%s" for _ in _MATCH_LOG_COLUMNS)})
ON CONFLICT (team_name, season, match_date, opponent) DO NOTHING
"""


def insert_match_logs(conn, match_rows: list[dict[str, Any]]) -> int:
    if not match_rows:
        return 0
    cursor = conn.cursor()
    inserted = 0
    for row in match_rows:
        params = [row.get(col) for col in _MATCH_LOG_COLUMNS]
        cursor.execute(_MATCH_LOG_INSERT_SQL, params)
        inserted += cursor.rowcount if cursor.rowcount and cursor.rowcount > 0 else 0
    conn.commit()
    return inserted


# -----------------------------------------------------------------------------
# Pipeline run tracking / match-log team rotation
# -----------------------------------------------------------------------------

def get_next_matchlog_team_index(conn) -> int:
    """Return the team-list index to start from for this run's match-log scrape."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT next_matchlog_team_index FROM PipelineRuns "
        "WHERE status = 'success' ORDER BY run_id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    return int(row[0]) if row else 0


def get_next_league_index(conn) -> int:
    """Return the leagues.json index to start from for this run's extra-league scrape."""
    cursor = conn.cursor()
    cursor.execute(
        "SELECT next_league_index FROM PipelineRuns "
        "WHERE status = 'success' ORDER BY run_id DESC LIMIT 1"
    )
    row = cursor.fetchone()
    return int(row[0]) if row else 0


def start_pipeline_run(conn) -> int:
    cursor = conn.cursor()
    cursor.execute("INSERT INTO PipelineRuns (status) VALUES ('running') RETURNING run_id")
    run_id = cursor.fetchone()[0]
    conn.commit()
    return int(run_id)


def finish_pipeline_run(
    conn,
    run_id: int,
    status: str,
    players_upserted: int = 0,
    team_stats_upserted: int = 0,
    match_logs_inserted: int = 0,
    next_matchlog_team_index: int = 0,
    next_league_index: int = 0,
    error_summary: Optional[str] = None,
) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE PipelineRuns
        SET run_finished_at = now(),
            status = %s,
            players_upserted = %s,
            team_stats_upserted = %s,
            match_logs_inserted = %s,
            next_matchlog_team_index = %s,
            next_league_index = %s,
            error_summary = %s
        WHERE run_id = %s
        """,
        [
            status,
            players_upserted,
            team_stats_upserted,
            match_logs_inserted,
            next_matchlog_team_index,
            next_league_index,
            (error_summary or "")[:4000] or None,
            run_id,
        ],
    )
    conn.commit()
