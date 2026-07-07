"""
One-time historical backfill: last 5 seasons of player + squad stats for all
10 leagues in `pipeline/all_leagues.json`, including the goalkeeping
(`keepers`/`keepersadv`), playing-time, and miscellaneous categories.

This is a standalone script, run manually - it is NOT part of the daily
timer-triggered Azure Function (`run_pipeline.py` / `fbref_daily_pipeline`).
Run it once (or occasionally re-run; upserts are idempotent) from `api/`:

    cd api
    export DATABASE_URL="<your Postgres connection string>"
    python -m pipeline.backfill_history

Or via GitHub Actions: run the "FBref pipeline" workflow manually with
job=backfill (uses the DATABASE_URL repository secret).

Writes to:
- `dbo.PlayerSeasonStats` (upsert by `player_id` + `season`) - per-90 metrics
  plus goalkeeping/playing-time/misc fields, for every player in every
  league-season.
- `dbo.TeamStats` (upsert by `team_name` + `season`) - squad-level totals,
  reusing the table already populated by the daily pipeline (which only
  covers the current season).

Scope notes (see docs/FBREF_PIPELINE.md):
- Nationalities and squad/player wages pages are NOT scraped (out of scope).
- "Last 5 seasons" includes the current season plus the 4 prior seasons, so
  `dbo.PlayerSeasonStats` is fully populated even before the daily pipeline
  (Task: wire PlayerSeasonStats into run_pipeline.py) writes current-season
  rows.

This is a heavy operation: 10 leagues x 5 seasons x ~10 page fetches (one per
stat category; squad stats share the "standard" page so add no extra
fetches), at FBref's enforced crawl delay (default 6s) -> roughly 500
fetches, ~50 minutes. Safe to interrupt (Ctrl-C) and re-run later; already
loaded league-seasons are simply re-upserted.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import requests

from shared.config import get_settings

from . import fbref_scraper, load_azure_sql, transform

logger = logging.getLogger("footballq.pipeline.backfill_history")

_ALL_LEAGUES_PATH = os.path.join(os.path.dirname(__file__), "all_leagues.json")

SEASONS_BACK = 5


def _load_all_leagues() -> list[dict[str, Any]]:
    with open(_ALL_LEAGUES_PATH, encoding="utf-8") as f:
        return json.load(f)


def _season_sequence(season_format: str, current_season: str, count: int = SEASONS_BACK) -> list[str]:
    """Return `count` season strings starting at `current_season` and going
    backwards, in the league's format ("YYYY-YYYY" or "YYYY")."""
    if season_format == "YYYY-YYYY":
        start_year = int(current_season.split("-")[0])
        return [f"{start_year - i}-{start_year - i + 1}" for i in range(count)]
    start_year = int(current_season)
    return [str(start_year - i) for i in range(count)]


def run() -> dict[str, Any]:
    settings = get_settings()
    summary: dict[str, Any] = {
        "status": "skipped",
        "player_season_rows_upserted": 0,
        "team_stats_upserted": 0,
        "league_seasons_processed": 0,
        "errors": [],
    }

    if not settings.database_configured:
        summary["reason"] = "DATABASE_URL is not configured"
        return summary

    conn = load_azure_sql.get_connection(settings.database_url)
    summary["status"] = "success"

    session = requests.Session()
    rate_limiter = fbref_scraper.build_rate_limiter(session)

    leagues = _load_all_leagues()
    for league in leagues:
        league_name = league["league_name"]
        comp_id = league["fbref_comp_id"]
        slug = league["fbref_slug"]
        seasons = _season_sequence(league["season_format"], league["current_season"])

        for season in seasons:
            # Current season uses the no-season-segment URL; past seasons use
            # /en/comps/{id}/{season}/{type}/{season}-{slug}-Stats.
            season_arg = None if season == league["current_season"] else season
            try:
                players_df = fbref_scraper.scrape_league_player_stats(
                    comp_id, slug, session, rate_limiter, season=season_arg
                )
                player_rows = transform.transform_player_season_stats(
                    players_df, season, league_name_override=league_name
                )
                summary["player_season_rows_upserted"] += load_azure_sql.upsert_player_season_stats(
                    conn, player_rows
                )

                squads_df = fbref_scraper.scrape_league_squad_stats(
                    comp_id, slug, session, rate_limiter, season=season_arg
                )
                team_rows = transform.transform_team_stats(squads_df, season, league_name_override=league_name)
                summary["team_stats_upserted"] += load_azure_sql.upsert_team_stats(conn, team_rows)

                logger.info("%s %s: %d players, %d teams", league_name, season, len(player_rows), len(team_rows))
                print(f"{league_name} {season}: {len(player_rows)} players, {len(team_rows)} teams")
            except Exception as exc:  # pragma: no cover - network/driver dependent
                logger.exception("Failed %s %s", league_name, season)
                summary["errors"].append(f"{league_name} {season}: {type(exc).__name__}: {exc}")
                summary["status"] = "partial"

            summary["league_seasons_processed"] += 1

    conn.close()
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run()
    print(json.dumps(result, indent=2))
