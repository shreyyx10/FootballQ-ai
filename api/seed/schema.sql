-- =============================================================================
-- FootballQ AI - PostgreSQL Schema (Neon / Supabase free tier)
-- =============================================================================
-- Apply with:  python -m seed.apply_schema   (from api/, DATABASE_URL set)
-- or:          psql "$DATABASE_URL" -f seed/schema.sql
--
-- Notes:
--   - Ported from the original Azure SQL / T-SQL schema (see git history).
--   - This script is idempotent: it drops existing tables first so it can be
--     re-run safely during development.
-- =============================================================================

DROP TABLE IF EXISTS ApiLogs CASCADE;
DROP TABLE IF EXISTS ScoutQueries CASCADE;
DROP TABLE IF EXISTS ScoutingNotes CASCADE;
DROP TABLE IF EXISTS TeamProfiles CASCADE;
DROP TABLE IF EXISTS MatchLogs CASCADE;
DROP TABLE IF EXISTS PlayerSeasonStats CASCADE;
DROP TABLE IF EXISTS TeamStats CASCADE;
DROP TABLE IF EXISTS PipelineRuns CASCADE;
DROP TABLE IF EXISTS Players CASCADE;

-- -----------------------------------------------------------------------------
-- Players: structured football statistics (per-90 metrics, market value, etc.)
-- -----------------------------------------------------------------------------
CREATE TABLE Players (
    player_id                    VARCHAR(50)   NOT NULL PRIMARY KEY,
    player_name                  VARCHAR(150)  NOT NULL,
    age                          INT           NULL,
    nationality                  VARCHAR(100)  NULL,
    club                         VARCHAR(150)  NULL,
    league                       VARCHAR(150)  NULL,
    position                     VARCHAR(100)  NULL,
    minutes                      INT           NULL,
    goals                        INT           NULL,
    assists                      INT           NULL,
    xg                           DOUBLE PRECISION NULL,
    xag                          DOUBLE PRECISION NULL,
    shots_per90                  DOUBLE PRECISION NULL,
    key_passes_per90             DOUBLE PRECISION NULL,
    progressive_passes_per90     DOUBLE PRECISION NULL,
    progressive_carries_per90    DOUBLE PRECISION NULL,
    successful_takeons_per90     DOUBLE PRECISION NULL,
    shot_creating_actions_per90  DOUBLE PRECISION NULL,
    tackles_per90                DOUBLE PRECISION NULL,
    interceptions_per90          DOUBLE PRECISION NULL,
    pressures_per90              DOUBLE PRECISION NULL,
    pass_completion_pct          DOUBLE PRECISION NULL,
    market_value_million         DOUBLE PRECISION NULL,
    preferred_foot               VARCHAR(20)   NULL
);

CREATE INDEX IX_Players_Position ON Players(position);
CREATE INDEX IX_Players_League ON Players(league);
CREATE INDEX IX_Players_Club ON Players(club);

-- -----------------------------------------------------------------------------
-- ScoutingNotes: free-text scouting context used for SQL-backed RAG retrieval
-- -----------------------------------------------------------------------------
CREATE TABLE ScoutingNotes (
    note_id          INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    player_id        VARCHAR(50)   NOT NULL,
    player_name      VARCHAR(150)  NOT NULL,
    profile_summary  TEXT          NULL,
    strengths        TEXT          NULL,
    weaknesses       TEXT          NULL,
    tactical_notes   TEXT          NULL,
    role_fit         TEXT          NULL,
    risk_notes       TEXT          NULL,
    CONSTRAINT FK_ScoutingNotes_Players FOREIGN KEY (player_id)
        REFERENCES Players(player_id)
);

CREATE INDEX IX_ScoutingNotes_PlayerId ON ScoutingNotes(player_id);

-- -----------------------------------------------------------------------------
-- TeamProfiles: tactical identity used for tactical-fit analysis and RAG
-- -----------------------------------------------------------------------------
CREATE TABLE TeamProfiles (
    team_id              INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    team_name            VARCHAR(150)  NOT NULL UNIQUE,
    tactical_style       TEXT          NULL,
    formation            VARCHAR(50)   NULL,
    pressing_intensity   VARCHAR(50)   NULL,
    possession_style     VARCHAR(100)  NULL,
    player_requirements  TEXT          NULL
);

-- -----------------------------------------------------------------------------
-- TeamStats: per-season squad-level statistics from the FBref data pipeline
-- (see docs/FBREF_PIPELINE.md). Distinct from TeamProfiles, which holds
-- curated narrative tactical-identity text used by the tactical-fit agent.
-- -----------------------------------------------------------------------------
CREATE TABLE TeamStats (
    team_stats_id   INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    team_name       VARCHAR(150)  NOT NULL,
    league          VARCHAR(150)  NULL,
    season          VARCHAR(20)   NOT NULL,
    matches_played  INT           NULL,
    goals_for       INT           NULL,
    goals_against   INT           NULL,
    xg              DOUBLE PRECISION NULL,
    xga             DOUBLE PRECISION NULL,
    possession_pct  DOUBLE PRECISION NULL,
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT UQ_TeamStats_Team_Season UNIQUE (team_name, season)
);

CREATE INDEX IX_TeamStats_League ON TeamStats(league);

-- -----------------------------------------------------------------------------
-- PlayerSeasonStats: per-season player statistics from the FBref data
-- pipeline (see docs/FBREF_PIPELINE.md), including the goalkeeping,
-- playing-time, and miscellaneous categories not carried by Players
-- (which holds only the current-season "snapshot" used by the live app).
-- Additive table - does not affect Players' existing API/frontend
-- contract. Populated by the one-time historical backfill
-- (pipeline/backfill_history.py, last 5 seasons) and refreshed for the
-- current season by the daily pipeline.
-- -----------------------------------------------------------------------------
CREATE TABLE PlayerSeasonStats (
    player_season_id            INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    player_id                   VARCHAR(50)   NOT NULL,
    player_name                 VARCHAR(150)  NOT NULL,
    season                      VARCHAR(20)   NOT NULL,
    league                      VARCHAR(150)  NULL,
    club                        VARCHAR(150)  NULL,
    position                    VARCHAR(100)  NULL,
    nationality                 VARCHAR(100)  NULL,
    age                         INT           NULL,
    -- existing per-90 / season metrics (mirrors Players)
    minutes                     INT           NULL,
    goals                       INT           NULL,
    assists                     INT           NULL,
    xg                          DOUBLE PRECISION NULL,
    xag                         DOUBLE PRECISION NULL,
    shots_per90                 DOUBLE PRECISION NULL,
    key_passes_per90            DOUBLE PRECISION NULL,
    progressive_passes_per90    DOUBLE PRECISION NULL,
    progressive_carries_per90   DOUBLE PRECISION NULL,
    successful_takeons_per90    DOUBLE PRECISION NULL,
    shot_creating_actions_per90 DOUBLE PRECISION NULL,
    tackles_per90               DOUBLE PRECISION NULL,
    interceptions_per90         DOUBLE PRECISION NULL,
    pass_completion_pct         DOUBLE PRECISION NULL,
    -- goalkeeping (keepers + keepersadv)
    gk_goals_against_per90      DOUBLE PRECISION NULL,
    gk_save_pct                 DOUBLE PRECISION NULL,
    gk_clean_sheet_pct          DOUBLE PRECISION NULL,
    gk_psxg                     DOUBLE PRECISION NULL,
    -- playing time
    starts                      INT           NULL,
    minutes_per_match           DOUBLE PRECISION NULL,
    minutes_pct                 DOUBLE PRECISION NULL,
    -- miscellaneous
    yellow_cards                INT           NULL,
    red_cards                   INT           NULL,
    fouls_committed_per90       DOUBLE PRECISION NULL,
    fouls_drawn_per90           DOUBLE PRECISION NULL,
    offsides_per90              DOUBLE PRECISION NULL,
    aerials_won_pct             DOUBLE PRECISION NULL,
    ball_recoveries_per90       DOUBLE PRECISION NULL,
    updated_at                  TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT UQ_PlayerSeasonStats_Player_Season UNIQUE (player_id, season)
);

CREATE INDEX IX_PlayerSeasonStats_League_Season ON PlayerSeasonStats(league, season);

-- -----------------------------------------------------------------------------
-- MatchLogs: per-match results from the FBref data pipeline, used for
-- trend/form analysis (see docs/FBREF_PIPELINE.md).
-- -----------------------------------------------------------------------------
CREATE TABLE MatchLogs (
    match_log_id    INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    team_name       VARCHAR(150)  NOT NULL,
    season          VARCHAR(20)   NOT NULL,
    match_date      DATE          NOT NULL,
    competition     VARCHAR(100)  NULL,
    venue           VARCHAR(10)   NULL,  -- 'Home' or 'Away'
    opponent        VARCHAR(150)  NULL,
    result          VARCHAR(10)   NULL,  -- 'W', 'D', or 'L'
    goals_for       INT           NULL,
    goals_against   INT           NULL,
    xg              DOUBLE PRECISION NULL,
    xga             DOUBLE PRECISION NULL,
    possession_pct  DOUBLE PRECISION NULL,
    updated_at      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    CONSTRAINT UQ_MatchLogs_Team_Season_Date_Opponent
        UNIQUE (team_name, season, match_date, opponent)
);

CREATE INDEX IX_MatchLogs_Team_Season ON MatchLogs(team_name, season);

-- -----------------------------------------------------------------------------
-- PipelineRuns: observability + rotation state for the daily FBref pipeline.
-- next_matchlog_team_index lets the scheduled job rotate through the
-- configured team list across runs instead of scraping everything at once.
-- next_league_index does the same for pipeline/leagues.json - the extra
-- (non-Big5) leagues' player/squad stats are scraped one league per run.
-- -----------------------------------------------------------------------------
CREATE TABLE PipelineRuns (
    run_id                    INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_started_at            TIMESTAMPTZ   NOT NULL DEFAULT now(),
    run_finished_at           TIMESTAMPTZ   NULL,
    status                    VARCHAR(20)   NOT NULL DEFAULT 'running', -- running|success|partial|failed
    players_upserted          INT           NULL,
    team_stats_upserted       INT           NULL,
    match_logs_inserted       INT           NULL,
    next_matchlog_team_index  INT           NOT NULL DEFAULT 0,
    next_league_index         INT           NOT NULL DEFAULT 0,
    error_summary             TEXT          NULL
);

-- -----------------------------------------------------------------------------
-- ScoutQueries: log of natural-language queries sent to /api/scout
-- -----------------------------------------------------------------------------
CREATE TABLE ScoutQueries (
    query_id          INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    query_text        VARCHAR(1000) NOT NULL,
    created_at        TIMESTAMPTZ   NOT NULL DEFAULT now(),
    response_summary  TEXT          NULL
);

-- -----------------------------------------------------------------------------
-- ApiLogs: lightweight structured request logging for observability
-- -----------------------------------------------------------------------------
CREATE TABLE ApiLogs (
    log_id         INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    endpoint       VARCHAR(200)  NOT NULL,
    status_code    INT           NOT NULL,
    created_at     TIMESTAMPTZ   NOT NULL DEFAULT now(),
    error_summary  TEXT          NULL
);
