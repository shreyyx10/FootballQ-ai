"""
FBref pipeline orchestrator.

Used by:
- The daily timer-triggered Azure Function (`fbref_daily_pipeline` in
  function_app.py).
- Manual/local runs: `python -m pipeline.run_pipeline` from `api/`.

Behaviour:
1. No-ops (returns a summary with status "skipped") unless
   `FBREF_PIPELINE_ENABLED=true` AND `AZURE_SQL_CONNECTION_STRING` is set.
   This keeps the default deployment a pure read-only demo.
2. Scrapes & upserts Big5 player season stats -> dbo.Players.
3. Scrapes & upserts Big5 squad stats -> dbo.TeamStats.
4. Scrapes & upserts player + squad stats for a rotating slice of
   `leagues.json` (extra leagues beyond the Big 5) -> dbo.Players /
   dbo.TeamStats.
5. Scrapes match logs for a small, rotating slice of `teams.json` ->
   dbo.MatchLogs (keeps each run within the Azure Functions Consumption
   timeout - see docs/FBREF_PIPELINE.md).
6. Records a row in dbo.PipelineRuns regardless of outcome.

Every step is wrapped so that a failure in one (e.g. FBref temporarily
unreachable) doesn't prevent the others from running, and never raises out
of `run()` - the timer function logs the summary and returns.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import requests

from shared.config import get_settings

from . import fbref_scraper, load_azure_sql, transform

logger = logging.getLogger("footballq.pipeline.run_pipeline")

_TEAMS_PATH = os.path.join(os.path.dirname(__file__), "teams.json")
_LEAGUES_PATH = os.path.join(os.path.dirname(__file__), "leagues.json")


def _load_teams() -> list[dict[str, str]]:
    try:
        with open(_TEAMS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.error("Could not load teams.json: %s", type(exc).__name__)
        return []


def _load_leagues() -> list[dict[str, Any]]:
    try:
        with open(_LEAGUES_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.error("Could not load leagues.json: %s", type(exc).__name__)
        return []


def run() -> dict[str, Any]:
    settings = get_settings()
    summary: dict[str, Any] = {
        "status": "skipped",
        "players_upserted": 0,
        "team_stats_upserted": 0,
        "player_season_stats_upserted": 0,
        "match_logs_inserted": 0,
        "errors": [],
    }

    if not settings.fbref_pipeline_enabled:
        summary["reason"] = "FBREF_PIPELINE_ENABLED is not true"
        return summary
    if not settings.database_configured:
        summary["reason"] = "DATABASE_URL is not configured"
        return summary

    conn = load_azure_sql.get_connection(settings.database_url)
    run_id = load_azure_sql.start_pipeline_run(conn)
    summary["status"] = "success"

    session = requests.Session()
    rate_limiter = fbref_scraper.build_rate_limiter(session)

    # 1. Player season stats
    # `players_df` now also includes the keepers/keepersadv/playingtime/misc
    # categories (added to BIG5_PLAYER_STAT_PAGES) - transform_players only
    # uses the columns it needs, and transform_player_season_stats picks up
    # the rest for dbo.PlayerSeasonStats (current season).
    try:
        players_df = fbref_scraper.scrape_big5_player_stats(session, rate_limiter)
        player_rows = transform.transform_players(players_df)
        summary["players_upserted"] = load_azure_sql.upsert_players(conn, player_rows)

        season_rows = transform.transform_player_season_stats(players_df, settings.fbref_season)
        summary["player_season_stats_upserted"] = load_azure_sql.upsert_player_season_stats(conn, season_rows)
    except Exception as exc:  # pragma: no cover - network/driver dependent
        logger.exception("Player stats step failed")
        summary["errors"].append(f"players: {type(exc).__name__}: {exc}")
        summary["status"] = "partial"

    # 2. Squad stats
    try:
        squads_df = fbref_scraper.scrape_big5_squad_stats(session, rate_limiter)
        team_rows = transform.transform_team_stats(squads_df, settings.fbref_season)
        summary["team_stats_upserted"] = load_azure_sql.upsert_team_stats(conn, team_rows)
    except Exception as exc:  # pragma: no cover
        logger.exception("Squad stats step failed")
        summary["errors"].append(f"team_stats: {type(exc).__name__}: {exc}")
        summary["status"] = "partial"

    # 2b. Extra (non-Big5) leagues - rotate through leagues.json, one or two
    # leagues per run so each run stays well inside the 10-minute timeout.
    # Player + squad stats for a given league refresh every few days rather
    # than daily (see docs/FBREF_PIPELINE.md).
    next_league_index = 0
    try:
        leagues = _load_leagues()
        if leagues:
            start = load_azure_sql.get_next_league_index(conn) % len(leagues)
            batch_size = max(settings.fbref_extra_leagues_per_run, 1)
            for offset in range(batch_size):
                league = leagues[(start + offset) % len(leagues)]
                league_name = league["league_name"]
                season = league.get("season") or settings.fbref_season

                league_players_df = fbref_scraper.scrape_league_player_stats(
                    league["fbref_comp_id"], league["fbref_slug"], session, rate_limiter
                )
                league_player_rows = transform.transform_players(league_players_df, league_name_override=league_name)
                summary["players_upserted"] += load_azure_sql.upsert_players(conn, league_player_rows)

                league_season_rows = transform.transform_player_season_stats(
                    league_players_df, season, league_name_override=league_name
                )
                summary["player_season_stats_upserted"] += load_azure_sql.upsert_player_season_stats(
                    conn, league_season_rows
                )

                league_squads_df = fbref_scraper.scrape_league_squad_stats(
                    league["fbref_comp_id"], league["fbref_slug"], session, rate_limiter
                )
                league_team_rows = transform.transform_team_stats(league_squads_df, season, league_name_override=league_name)
                summary["team_stats_upserted"] += load_azure_sql.upsert_team_stats(conn, league_team_rows)
            next_league_index = (start + batch_size) % len(leagues)
    except Exception as exc:  # pragma: no cover
        logger.exception("Extra leagues step failed")
        summary["errors"].append(f"extra_leagues: {type(exc).__name__}: {exc}")
        summary["status"] = "partial"

    # 3. Match logs - rotate through teams.json, a few per run
    next_index = 0
    try:
        teams = _load_teams()
        if teams:
            start = load_azure_sql.get_next_matchlog_team_index(conn) % len(teams)
            batch_size = max(settings.fbref_matchlog_teams_per_run, 1)
            for offset in range(batch_size):
                team = teams[(start + offset) % len(teams)]
                match_df = fbref_scraper.scrape_team_match_log(
                    team["fbref_id"], team["fbref_slug"], settings.fbref_season, session, rate_limiter
                )
                match_rows = transform.transform_match_logs(match_df, team["team_name"], settings.fbref_season)
                summary["match_logs_inserted"] += load_azure_sql.insert_match_logs(conn, match_rows)
            next_index = (start + batch_size) % len(teams)
    except Exception as exc:  # pragma: no cover
        logger.exception("Match log step failed")
        summary["errors"].append(f"match_logs: {type(exc).__name__}: {exc}")
        summary["status"] = "partial"

    # A run that upserted nothing is not a success, even if no step raised -
    # e.g. every fetch failed/parsed empty (this happened when FBref started
    # returning 403 to scripts: all tables skipped "gracefully", 0 rows).
    if summary["status"] == "success" and summary["players_upserted"] == 0:
        summary["status"] = "partial"
        summary["errors"].append("players: 0 rows upserted (all fetches failed or parsed empty)")

    load_azure_sql.finish_pipeline_run(
        conn,
        run_id,
        status=summary["status"],
        players_upserted=summary["players_upserted"],
        team_stats_upserted=summary["team_stats_upserted"],
        match_logs_inserted=summary["match_logs_inserted"],
        next_matchlog_team_index=next_index,
        next_league_index=next_league_index,
        error_summary="; ".join(summary["errors"]) or None,
    )
    conn.close()
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
