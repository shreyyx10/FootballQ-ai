"""
FBref data pipeline for FootballQ AI (optional).

This package scrapes publicly available season stats, squad stats, and
match logs from FBref (https://fbref.com) and loads them into Azure SQL on
a daily schedule. It is entirely optional: the API and frontend work fully
without it (using the bundled sample data / LocalSeedDataStore).

See docs/FBREF_PIPELINE.md for:
- Why "every second" updates are neither possible nor useful (FBref rate
  limits, and stats only change after matches are played).
- Rate-limiting / robots.txt compliance.
- Configuration (FBREF_PIPELINE_ENABLED, FBREF_SEASON, etc.).
- The new TeamStats / MatchLogs / PipelineRuns tables (api/seed/schema.sql).

Modules:
    fbref_scraper - rate-limited HTTP fetch + FBref table parsing.
    transform      - map raw FBref tables to FootballQ AI schema rows.
    load_azure_sql - parameterised upsert/insert helpers for Azure SQL.
    run_pipeline   - orchestrator used by the timer-triggered function and CLI.
"""
