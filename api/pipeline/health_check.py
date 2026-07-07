"""
Pipeline health check: one read-only pass over Azure SQL that answers
"is the data layer actually live and complete?"

Reports:
- Last 5 PipelineRuns (status, timings, rows upserted, errors)
- Row counts for Players, PlayerSeasonStats, TeamStats, MatchLogs
- PlayerSeasonStats coverage: distinct league x season combinations vs the
  50 expected from the backfill (10 leagues x 5 seasons)
- Staleness: hours since the last successful run

Run locally from `api/` (same setup as backfill_history.py):

    cd api
    export DATABASE_URL="<your Postgres connection string>"
    python -m pipeline.health_check
"""

from __future__ import annotations

from shared.config import get_settings

from . import load_azure_sql

EXPECTED_LEAGUES = 10
EXPECTED_SEASONS_PER_LEAGUE = 5


def run() -> int:
    settings = get_settings()
    if not settings.database_configured:
        print("FAIL: DATABASE_URL is not configured")
        return 1

    conn = load_azure_sql.get_connection(settings.database_url)
    cur = conn.cursor()
    problems: list[str] = []

    print("=== Recent pipeline runs ===")
    cur.execute(
        """
        SELECT run_id, run_started_at, run_finished_at, status,
               players_upserted, team_stats_upserted, match_logs_inserted,
               error_summary
        FROM PipelineRuns ORDER BY run_started_at DESC LIMIT 5
        """
    )
    runs = cur.fetchall()
    if not runs:
        problems.append("PipelineRuns is empty - the scheduled pipeline has never recorded a run")
    for run_id, started, _finished, status, players, teams, matchlogs, errors in runs:
        print(
            f"  #{run_id} {started:%Y-%m-%d %H:%M} status={status} "
            f"players={players} teams={teams} matchlogs={matchlogs}"
        )
        if errors:
            print(f"      errors: {errors[:200]}")
    if runs and runs[0][3] == "failed":
        problems.append("Most recent run FAILED")

    cur.execute(
        """
        SELECT EXTRACT(epoch FROM (now() - MAX(run_started_at))) / 3600
        FROM PipelineRuns WHERE status IN ('success', 'partial')
        """
    )
    hours = cur.fetchone()[0]
    if hours is None:
        problems.append("No successful run has ever completed")
    elif hours > 48:
        problems.append(f"Last successful run was {hours:.0f}h ago (expected daily)")
    else:
        print(f"\nLast successful run: {hours:.0f}h ago")

    print("\n=== Row counts ===")
    for table in ("Players", "PlayerSeasonStats", "TeamStats", "MatchLogs"):
        cur.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608 - fixed names
        n = cur.fetchone()[0]
        print(f"  {table}: {n:,}")
        if n == 0 and table != "MatchLogs":
            problems.append(f"{table} is empty")

    print("\n=== PlayerSeasonStats coverage (league x season) ===")
    cur.execute(
        """
        SELECT league, COUNT(DISTINCT season) AS seasons, COUNT(*) AS n_rows
        FROM PlayerSeasonStats GROUP BY league ORDER BY league
        """
    )
    rows = cur.fetchall()
    for league, seasons, n_rows in rows:
        flag = "" if seasons >= EXPECTED_SEASONS_PER_LEAGUE else "  <- fewer seasons than backfill target"
        print(f"  {league}: {seasons} seasons, {n_rows:,} rows{flag}")
    if len(rows) < EXPECTED_LEAGUES:
        problems.append(
            f"Only {len(rows)}/{EXPECTED_LEAGUES} leagues present in PlayerSeasonStats - "
            "backfill_history.py may not have been run (or not completed)"
        )

    conn.close()

    print("\n=== Verdict ===")
    if problems:
        for p in problems:
            print(f"  PROBLEM: {p}")
        return 1
    print("  OK: pipeline data layer looks healthy")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
