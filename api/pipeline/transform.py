"""
Transform FBref tables (as returned by `fbref_scraper`) into row dicts
matching the FootballQ AI schema (api/seed/schema.sql).

Design notes:
- Functions here are pure (DataFrame/dict in, list[dict] out) and have no
  network or database dependencies, so they're fully unit-testable with
  small synthetic DataFrames (see api/tests/test_pipeline_transform.py).
- Per-90 metrics that FBref only publishes as season totals (e.g. key
  passes, progressive passes/carries, successful take-ons, tackles,
  interceptions) are divided by the player's "90s" (matches-equivalent)
  here, to populate the *_per90 fields in dbo.Players.
- Some fields in dbo.Players have no FBref source and are intentionally
  left as None:
    - `pressures_per90`: FBref/Big5 no longer publishes pressure data
      (the underlying StatsBomb defensive-actions feed was discontinued
      for these leagues). Left NULL; see docs/FBREF_PIPELINE.md.
    - `market_value_million`: not published by FBref at all (would need a
      separate source such as Transfermarkt - out of scope).
    - `preferred_foot`: not present in the scraped tables.
  These columns remain NULLable in the schema for exactly this reason.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Optional

import pandas as pd


# -----------------------------------------------------------------------------
# Small parsing helpers (FBref formats numbers/text inconsistently)
# -----------------------------------------------------------------------------

def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, float) and pd.isna(value):
        return None
    text = str(value).strip().replace(",", "")
    if text in {"", "nan", "—", "-"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_int(value: Any) -> Optional[int]:
    as_float = _to_float(value)
    return int(as_float) if as_float is not None else None


def _parse_age(value: Any) -> Optional[int]:
    """FBref ages are formatted like '24-103' (years-days); take the years part."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return _to_int(text.split("-")[0])


def _parse_country_code(value: Any) -> Optional[str]:
    """FBref nation/league cells look like 'es ESP' or 'eng Premier League'; take the last token(s)."""
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    parts = text.split(" ", 1)
    return parts[-1].strip() if len(parts) > 1 else text


def slugify(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", value.strip().lower())
    return re.sub(r"_+", "_", text).strip("_")


def generate_player_id(player_name: str, born: Any, squad: Any) -> str:
    """Deterministic player_id for a scraped player.

    FBref's own numeric player IDs aren't exposed by `pandas.read_html`
    (they live in `href` attributes that read_html drops), so we derive a
    stable id from name + birth year + squad. This is stable across daily
    runs (so upserts update the same row) as long as the player's name and
    birth year don't change.
    """
    basis = f"{player_name}|{born}|{squad}".lower()
    digest = hashlib.sha1(basis.encode("utf-8")).hexdigest()[:10]
    return f"fb_{slugify(player_name)[:30]}_{digest}"


# -----------------------------------------------------------------------------
# Players
# -----------------------------------------------------------------------------

# Maps dbo.Players columns -> flattened FBref column name(s). A tuple means
# "numerator, denominator" - the value is divided to produce a per-90 figure.
_PLAYER_DIRECT_FIELDS: dict[str, str] = {
    "minutes": "Min",
    "goals": "Gls",
    "assists": "Ast",
    "xg": "xG",
    "xag": "xAG",
    "shots_per90": "Sh/90",
    "pass_completion_pct": "Cmp%",
}

_PLAYER_PER90_FIELDS: dict[str, str] = {
    "key_passes_per90": "KP",
    "progressive_passes_per90": "PrgP",
    "progressive_carries_per90": "PrgC",
    "successful_takeons_per90": "Succ",
    "tackles_per90": "Tkl",
    "interceptions_per90": "Int",
}

# shot_creating_actions_per90 comes pre-computed from the GCA table.
_PLAYER_PER90_DIRECT_FIELDS: dict[str, str] = {
    "shot_creating_actions_per90": "SCA90",
}

# Goalkeeping fields (from the `keepers` + `keepersadv` tables), used by
# transform_player_season_stats only. FBref already publishes these as
# per-90/percentage figures, so no division is needed. NOTE: column names
# are best-effort based on FBref's standard schema - verify against a live
# scrape on first run (see docs/FBREF_PIPELINE.md).
_PLAYER_GK_DIRECT_FIELDS: dict[str, str] = {
    "gk_goals_against_per90": "GA90",
    "gk_save_pct": "Save%",
    "gk_clean_sheet_pct": "CS%",
    "gk_psxg": "PSxG",
}

# Playing-time fields (from the `playingtime` table), used by
# transform_player_season_stats only.
_PLAYER_PLAYING_TIME_FIELDS: dict[str, str] = {
    "starts": "Starts",
    "minutes_per_match": "Mn/MP",
    "minutes_pct": "Min%",
}

# Miscellaneous fields (from the `misc` table), used by
# transform_player_season_stats only. Cards are season totals; the rest are
# divided by "90s" to produce per-90 figures.
_PLAYER_MISC_DIRECT_FIELDS: dict[str, str] = {
    "yellow_cards": "CrdY",
    "red_cards": "CrdR",
    "aerials_won_pct": "Won%",
}

_PLAYER_MISC_PER90_FIELDS: dict[str, str] = {
    "fouls_committed_per90": "Fls",
    "fouls_drawn_per90": "Fld",
    "offsides_per90": "Off",
    "ball_recoveries_per90": "Recov",
}


def _player_identity_fields(record: pd.Series, league_name_override: Optional[str] = None) -> dict[str, Any]:
    """Shared identity/metadata fields for a player row (used by both
    transform_players and transform_player_season_stats)."""
    player_name = str(record.get("Player", "")).strip()
    return {
        "player_id": generate_player_id(player_name, record.get("Born"), record.get("Squad")),
        "player_name": player_name,
        "age": _parse_age(record.get("Age")),
        "nationality": _parse_country_code(record.get("Nation")),
        "club": str(record.get("Squad", "") or "").strip() or None,
        "league": league_name_override or _parse_country_code(record.get("Comp")),
        "position": str(record.get("Pos", "") or "").strip() or None,
    }


def _player_core_stat_fields(record: pd.Series, nineties: Optional[float]) -> dict[str, Any]:
    """Shared per-90/season-total stat fields (existing dbo.Players metrics,
    also reused as the base of dbo.PlayerSeasonStats rows)."""
    row: dict[str, Any] = {}

    for schema_field, fbref_col in _PLAYER_DIRECT_FIELDS.items():
        row[schema_field] = _to_int(record.get(fbref_col)) if schema_field == "minutes" else _to_float(record.get(fbref_col))

    for schema_field, fbref_col in _PLAYER_PER90_DIRECT_FIELDS.items():
        row[schema_field] = _to_float(record.get(fbref_col))

    for schema_field, fbref_col in _PLAYER_PER90_FIELDS.items():
        total = _to_float(record.get(fbref_col))
        if total is not None and nineties:
            row[schema_field] = round(total / nineties, 2)
        else:
            row[schema_field] = None

    if row["goals"] is None:
        row["goals"] = 0
    if row["assists"] is None:
        row["assists"] = 0

    return row


def transform_players(df: pd.DataFrame, league_name_override: Optional[str] = None) -> list[dict[str, Any]]:
    """Transform a merged player-stats DataFrame into dbo.Players rows.

    `df` is expected to be the output of
    `fbref_scraper.scrape_big5_player_stats()` or
    `fbref_scraper.scrape_league_player_stats()` (already flattened and with
    summary rows removed), but any DataFrame with the same column names
    works - this is what the unit tests pass in directly.

    `league_name_override`: for single-league pages (everything except the
    Big5 combined page), FBref's `Comp` column may be missing or inconsistent
    with our naming, so the caller passes the league's configured name (from
    `pipeline/leagues.json`) and it wins over any parsed `Comp` value.
    """
    rows: list[dict[str, Any]] = []
    if df is None or df.empty:
        return rows

    for _, record in df.iterrows():
        player_name = str(record.get("Player", "")).strip()
        if not player_name:
            continue

        nineties = _to_float(record.get("90s"))

        row: dict[str, Any] = {
            **_player_identity_fields(record, league_name_override),
            "pressures_per90": None,
            "market_value_million": None,
            "preferred_foot": None,
        }
        row.update(_player_core_stat_fields(record, nineties))

        rows.append(row)

    return rows


# -----------------------------------------------------------------------------
# Player season stats (per-season, includes goalkeeping/playing-time/misc)
# -----------------------------------------------------------------------------

def transform_player_season_stats(
    df: pd.DataFrame, season: str, league_name_override: Optional[str] = None
) -> list[dict[str, Any]]:
    """Transform a merged player-stats DataFrame into dbo.PlayerSeasonStats rows.

    `df` is expected to be the output of `fbref_scraper.scrape_league_player_stats()`
    (or the Big5 equivalent) merged across all categories, including the new
    `keepers`, `keepersadv`, `playingtime`, and `misc` tables - but works with
    any DataFrame with the same column names, including ones missing those
    columns (the new fields are simply left `None`).

    `season` (e.g. "2025-2026" or "2026" for calendar-year leagues) is stored
    on every row so the table can hold multiple seasons per player.

    `league_name_override`: see `transform_players`.
    """
    rows: list[dict[str, Any]] = []
    if df is None or df.empty:
        return rows

    for _, record in df.iterrows():
        player_name = str(record.get("Player", "")).strip()
        if not player_name:
            continue

        nineties = _to_float(record.get("90s"))

        row: dict[str, Any] = {
            **_player_identity_fields(record, league_name_override),
            "season": season,
        }
        row.update(_player_core_stat_fields(record, nineties))

        for schema_field, fbref_col in _PLAYER_GK_DIRECT_FIELDS.items():
            row[schema_field] = _to_float(record.get(fbref_col))

        for schema_field, fbref_col in _PLAYER_PLAYING_TIME_FIELDS.items():
            row[schema_field] = _to_int(record.get(fbref_col)) if schema_field == "starts" else _to_float(record.get(fbref_col))

        for schema_field, fbref_col in _PLAYER_MISC_DIRECT_FIELDS.items():
            value = record.get(fbref_col)
            row[schema_field] = _to_int(value) if schema_field in ("yellow_cards", "red_cards") else _to_float(value)

        for schema_field, fbref_col in _PLAYER_MISC_PER90_FIELDS.items():
            total = _to_float(record.get(fbref_col))
            if total is not None and nineties:
                row[schema_field] = round(total / nineties, 2)
            else:
                row[schema_field] = None

        rows.append(row)

    return rows


# -----------------------------------------------------------------------------
# Team stats (squad-level)
# -----------------------------------------------------------------------------

def transform_team_stats(
    df: pd.DataFrame, season: str, league_name_override: Optional[str] = None
) -> list[dict[str, Any]]:
    """Transform a squad standard-stats table into dbo.TeamStats rows.

    `goals_against` / `xga` are left None here because they come from
    FBref's separate "squads ... against" table, which is not scraped by
    default to keep each pipeline run small (see docs/FBREF_PIPELINE.md).

    `league_name_override`: see `transform_players` - for single-league
    squad-stats pages, the configured league name wins over any parsed
    `Comp` value.
    """
    rows: list[dict[str, Any]] = []
    if df is None or df.empty:
        return rows

    for _, record in df.iterrows():
        team_name = str(record.get("Squad", "")).strip()
        if not team_name:
            continue

        rows.append(
            {
                "team_name": team_name,
                "league": league_name_override or _parse_country_code(record.get("Comp")),
                "season": season,
                "matches_played": _to_int(record.get("MP")),
                "goals_for": _to_int(record.get("Gls")),
                "goals_against": _to_int(record.get("GA")),
                "xg": _to_float(record.get("xG")),
                "xga": _to_float(record.get("xGA")),
                "possession_pct": _to_float(record.get("Poss")),
            }
        )

    return rows


# -----------------------------------------------------------------------------
# Match logs
# -----------------------------------------------------------------------------

_RESULT_MAP = {"W": "W", "D": "D", "L": "L"}


def transform_match_logs(df: pd.DataFrame, team_name: str, season: str) -> list[dict[str, Any]]:
    """Transform a team's "Scores & Fixtures" match log into dbo.MatchLogs rows.

    Rows without a played result yet (future fixtures - empty `Result`/`GF`)
    are skipped, since MatchLogs is meant to reflect completed matches.
    """
    rows: list[dict[str, Any]] = []
    if df is None or df.empty:
        return rows

    for _, record in df.iterrows():
        result = str(record.get("Result", "") or "").strip()
        if result not in _RESULT_MAP:
            continue  # fixture not yet played

        date_value = record.get("Date")
        match_date = pd.to_datetime(date_value, errors="coerce")
        if pd.isna(match_date):
            continue

        rows.append(
            {
                "team_name": team_name,
                "season": season,
                "match_date": match_date.date().isoformat(),
                "competition": str(record.get("Comp", "") or "").strip() or None,
                "venue": str(record.get("Venue", "") or "").strip() or None,
                "opponent": str(record.get("Opponent", "") or "").strip() or None,
                "result": _RESULT_MAP[result],
                "goals_for": _to_int(record.get("GF")),
                "goals_against": _to_int(record.get("GA")),
                "xg": _to_float(record.get("xG")),
                "xga": _to_float(record.get("xGA")),
                "possession_pct": _to_float(record.get("Poss")),
            }
        )

    return rows
