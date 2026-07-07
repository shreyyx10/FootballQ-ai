"""
Data access layer for FootballQ AI.

Provides a small abstraction (`DataStore`) with two implementations:

1. `PostgresDataStore` - used when `DATABASE_URL` is set (free-tier
   PostgreSQL, e.g. Neon or Supabase). Uses `psycopg` with parameterised
   queries only (no string concatenation of user input into SQL).

2. `LocalSeedDataStore` - used when no database connection string is
   configured (e.g. during local development, CI, or before the database
   has been provisioned). Loads the same sample data that is used to seed
   the database (api/seed/sample_players.csv, sample_scouting_notes.json,
   sample_team_profiles.json) into memory.

This means the live website works in "free-demo" mode even before the
database is provisioned, satisfying the zero-cost / no-local-dependency
requirement.

Security notes:
- The connection string is never logged or returned to clients.
- All SQL queries use parameter placeholders (`%s`) - never f-strings
  or `.format()` with user input.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import threading
from dataclasses import asdict, dataclass
from typing import Any, Optional

from .config import get_settings

logger = logging.getLogger("footballq.database")

_SEED_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "seed")


# -----------------------------------------------------------------------------
# Shared filter dataclass
# -----------------------------------------------------------------------------

@dataclass
class PlayerFilters:
    position: Optional[str] = None
    league: Optional[str] = None
    club: Optional[str] = None
    age_min: Optional[int] = None
    age_max: Optional[int] = None
    minutes_min: Optional[int] = None

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


NUMERIC_FIELDS = {
    "age",
    "minutes",
    "goals",
    "assists",
    "xg",
    "xag",
    "shots_per90",
    "key_passes_per90",
    "progressive_passes_per90",
    "progressive_carries_per90",
    "successful_takeons_per90",
    "shot_creating_actions_per90",
    "tackles_per90",
    "interceptions_per90",
    "pressures_per90",
    "pass_completion_pct",
    "market_value_million",
}


def _coerce_player_row(row: dict[str, Any]) -> dict[str, Any]:
    """Coerce raw CSV/SQL row values into the correct Python types."""
    coerced: dict[str, Any] = {}
    for key, value in row.items():
        if value is None or value == "":
            coerced[key] = None
            continue
        if key in NUMERIC_FIELDS:
            try:
                if key in {"age", "minutes", "goals", "assists"}:
                    coerced[key] = int(float(value))
                else:
                    coerced[key] = float(value)
            except (ValueError, TypeError):
                coerced[key] = None
        else:
            coerced[key] = value
    return coerced


# -----------------------------------------------------------------------------
# Local seed-backed data store (default / fallback)
# -----------------------------------------------------------------------------

class LocalSeedDataStore:
    """In-memory data store backed by the bundled seed files.

    Used whenever AZURE_SQL_CONNECTION_STRING is not configured, so the
    public demo always works without any database provisioning step.
    """

    _lock = threading.Lock()
    _players: Optional[list[dict[str, Any]]] = None
    _scouting_notes: Optional[list[dict[str, Any]]] = None
    _team_profiles: Optional[list[dict[str, Any]]] = None

    def _load(self) -> None:
        if self._players is not None:
            return
        with self._lock:
            if self._players is not None:
                return

            players: list[dict[str, Any]] = []
            csv_path = os.path.join(_SEED_DIR, "sample_players.csv")
            try:
                with open(csv_path, newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        players.append(_coerce_player_row(row))
            except FileNotFoundError:
                logger.warning("sample_players.csv not found at %s", csv_path)

            notes: list[dict[str, Any]] = []
            notes_path = os.path.join(_SEED_DIR, "sample_scouting_notes.json")
            try:
                with open(notes_path, encoding="utf-8") as f:
                    notes = json.load(f)
            except FileNotFoundError:
                logger.warning("sample_scouting_notes.json not found at %s", notes_path)

            teams: list[dict[str, Any]] = []
            teams_path = os.path.join(_SEED_DIR, "sample_team_profiles.json")
            try:
                with open(teams_path, encoding="utf-8") as f:
                    teams = json.load(f)
            except FileNotFoundError:
                logger.warning("sample_team_profiles.json not found at %s", teams_path)

            type(self)._players = players
            type(self)._scouting_notes = notes
            type(self)._team_profiles = teams

    def get_players(self, filters: Optional[PlayerFilters] = None) -> list[dict[str, Any]]:
        self._load()
        players = list(self._players or [])
        if not filters:
            return players

        def matches(player: dict[str, Any]) -> bool:
            if filters.position and (player.get("position") or "").lower() != filters.position.lower():
                return False
            if filters.league and (player.get("league") or "").lower() != filters.league.lower():
                return False
            if filters.club and (player.get("club") or "").lower() != filters.club.lower():
                return False
            if filters.age_min is not None and (player.get("age") is None or player["age"] < filters.age_min):
                return False
            if filters.age_max is not None and (player.get("age") is None or player["age"] > filters.age_max):
                return False
            if filters.minutes_min is not None and (player.get("minutes") is None or player["minutes"] < filters.minutes_min):
                return False
            return True

        return [p for p in players if matches(p)]

    def get_player(self, player_id: str) -> Optional[dict[str, Any]]:
        self._load()
        for player in self._players or []:
            if player.get("player_id") == player_id:
                return player
        return None

    def get_scouting_notes(self, player_ids: Optional[list[str]] = None) -> list[dict[str, Any]]:
        self._load()
        notes = list(self._scouting_notes or [])
        if player_ids is None:
            return notes
        wanted = set(player_ids)
        return [n for n in notes if n.get("player_id") in wanted]

    def search_scouting_notes(self, keywords: list[str], limit: int = 5) -> list[dict[str, Any]]:
        """Simple weighted keyword search over scouting notes (SQL-backed RAG fallback)."""
        self._load()
        scored: list[tuple[float, dict[str, Any]]] = []
        for note in self._scouting_notes or []:
            score = _score_text_against_keywords(note, keywords)
            if score > 0:
                scored.append((score, note))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [note for _, note in scored[:limit]]

    def get_team_profiles(self) -> list[dict[str, Any]]:
        self._load()
        return list(self._team_profiles or [])

    def get_team_profile(self, team_name: str) -> Optional[dict[str, Any]]:
        self._load()
        for team in self._team_profiles or []:
            if (team.get("team_name") or "").lower() == team_name.lower():
                return team
        return None

    def search_team_profiles(self, keywords: list[str], limit: int = 3) -> list[dict[str, Any]]:
        self._load()
        scored: list[tuple[float, dict[str, Any]]] = []
        for team in self._team_profiles or []:
            score = _score_text_against_keywords(team, keywords)
            if score > 0:
                scored.append((score, team))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [team for _, team in scored[:limit]]

    # Logging is a no-op for the local seed store (no persistence target).
    def log_scout_query(self, query_text: str, response_summary: str) -> None:
        logger.info("scout_query logged (local mode, not persisted): %s", query_text[:120])

    def log_api_call(self, endpoint: str, status_code: int, error_summary: Optional[str] = None) -> None:
        logger.debug("api_log (local mode, not persisted): %s %s", endpoint, status_code)


_TEXT_FIELDS_FOR_SEARCH = [
    "profile_summary",
    "strengths",
    "weaknesses",
    "tactical_notes",
    "role_fit",
    "risk_notes",
    "tactical_style",
    "player_requirements",
    "possession_style",
    "team_name",
    "player_name",
]


def _score_text_against_keywords(record: dict[str, Any], keywords: list[str]) -> float:
    """Weighted keyword scoring used by the SQL-backed RAG retriever."""
    if not keywords:
        return 0.0
    score = 0.0
    haystacks: list[str] = []
    for field_name in _TEXT_FIELDS_FOR_SEARCH:
        value = record.get(field_name)
        if isinstance(value, str):
            haystacks.append(value.lower())
        elif isinstance(value, list):
            haystacks.append(" ".join(str(v) for v in value).lower())

    combined = " ".join(haystacks)
    for kw in keywords:
        kw_lower = kw.lower().strip()
        if not kw_lower:
            continue
        # Player/team name matches in profile_summary / team_name weigh more
        weight = 2.0 if kw_lower in (record.get("player_name", "") or "").lower() else 1.0
        weight = max(weight, 2.0 if kw_lower in (record.get("team_name", "") or "").lower() else 1.0)
        occurrences = combined.count(kw_lower)
        score += occurrences * weight
    return score


# -----------------------------------------------------------------------------
# PostgreSQL data store (used when DATABASE_URL is configured)
# -----------------------------------------------------------------------------

class PostgresDataStore:
    """PostgreSQL-backed data store using parameterised queries (psycopg)."""

    def __init__(self, connection_string: str):
        self._connection_string = connection_string
        self._fallback = LocalSeedDataStore()

    def _connect(self):
        import psycopg  # imported lazily so environments without psycopg can still run in local mode

        return psycopg.connect(self._connection_string, connect_timeout=10)

    def _rows_to_dicts(self, cursor) -> list[dict[str, Any]]:
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_players(self, filters: Optional[PlayerFilters] = None) -> list[dict[str, Any]]:
        try:
            query = "SELECT * FROM Players WHERE 1=1"
            params: list[Any] = []
            if filters:
                if filters.position:
                    query += " AND position = %s"
                    params.append(filters.position)
                if filters.league:
                    query += " AND league = %s"
                    params.append(filters.league)
                if filters.club:
                    query += " AND club = %s"
                    params.append(filters.club)
                if filters.age_min is not None:
                    query += " AND age >= %s"
                    params.append(filters.age_min)
                if filters.age_max is not None:
                    query += " AND age <= %s"
                    params.append(filters.age_max)
                if filters.minutes_min is not None:
                    query += " AND minutes >= %s"
                    params.append(filters.minutes_min)

            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                rows = self._rows_to_dicts(cursor)
            return [_coerce_player_row(row) for row in rows]
        except Exception as exc:  # pragma: no cover - network/driver dependent
            logger.error("Postgres get_players failed, falling back to seed data: %s", type(exc).__name__)
            return self._fallback.get_players(filters)

    def get_player(self, player_id: str) -> Optional[dict[str, Any]]:
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM Players WHERE player_id = %s", [player_id])
                rows = self._rows_to_dicts(cursor)
            return _coerce_player_row(rows[0]) if rows else None
        except Exception as exc:  # pragma: no cover
            logger.error("Postgres get_player failed, falling back to seed data: %s", type(exc).__name__)
            return self._fallback.get_player(player_id)

    def get_scouting_notes(self, player_ids: Optional[list[str]] = None) -> list[dict[str, Any]]:
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                if player_ids:
                    placeholders = ", ".join("%s" for _ in player_ids)
                    cursor.execute(
                        f"SELECT * FROM ScoutingNotes WHERE player_id IN ({placeholders})",
                        list(player_ids),
                    )
                else:
                    cursor.execute("SELECT * FROM ScoutingNotes")
                return self._rows_to_dicts(cursor)
        except Exception as exc:  # pragma: no cover
            logger.error("Postgres get_scouting_notes failed, falling back to seed data: %s", type(exc).__name__)
            return self._fallback.get_scouting_notes(player_ids)

    def search_scouting_notes(self, keywords: list[str], limit: int = 5) -> list[dict[str, Any]]:
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM ScoutingNotes")
                notes = self._rows_to_dicts(cursor)
        except Exception as exc:  # pragma: no cover
            logger.error("Postgres search_scouting_notes failed, falling back to seed data: %s", type(exc).__name__)
            return self._fallback.search_scouting_notes(keywords, limit)

        scored = [(score, n) for n in notes if (score := _score_text_against_keywords(n, keywords)) > 0]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [n for _, n in scored[:limit]]

    def get_team_profiles(self) -> list[dict[str, Any]]:
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM TeamProfiles")
                return self._rows_to_dicts(cursor)
        except Exception as exc:  # pragma: no cover
            logger.error("Postgres get_team_profiles failed, falling back to seed data: %s", type(exc).__name__)
            return self._fallback.get_team_profiles()

    def get_team_profile(self, team_name: str) -> Optional[dict[str, Any]]:
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM TeamProfiles WHERE team_name = %s", [team_name])
                rows = self._rows_to_dicts(cursor)
            return rows[0] if rows else None
        except Exception as exc:  # pragma: no cover
            logger.error("Postgres get_team_profile failed, falling back to seed data: %s", type(exc).__name__)
            return self._fallback.get_team_profile(team_name)

    def search_team_profiles(self, keywords: list[str], limit: int = 3) -> list[dict[str, Any]]:
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM TeamProfiles")
                teams = self._rows_to_dicts(cursor)
        except Exception as exc:  # pragma: no cover
            logger.error("Postgres search_team_profiles failed, falling back to seed data: %s", type(exc).__name__)
            return self._fallback.search_team_profiles(keywords, limit)

        scored = [(score, t) for t in teams if (score := _score_text_against_keywords(t, keywords)) > 0]
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [t for _, t in scored[:limit]]

    def log_scout_query(self, query_text: str, response_summary: str) -> None:
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO ScoutQueries (query_text, response_summary) VALUES (%s, %s)",
                    [query_text[:1000], response_summary[:4000]],
                )
                conn.commit()
        except Exception as exc:  # pragma: no cover
            logger.error("Postgres log_scout_query failed: %s", type(exc).__name__)

    def log_api_call(self, endpoint: str, status_code: int, error_summary: Optional[str] = None) -> None:
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO ApiLogs (endpoint, status_code, error_summary) VALUES (%s, %s, %s)",
                    [endpoint[:200], status_code, (error_summary or "")[:4000] or None],
                )
                conn.commit()
        except Exception as exc:  # pragma: no cover
            logger.error("Postgres log_api_call failed: %s", type(exc).__name__)


# Legacy alias (pre-Postgres migration name), kept so existing imports work.
AzureSqlDataStore = PostgresDataStore


# -----------------------------------------------------------------------------
# Factory
# -----------------------------------------------------------------------------

_data_store = None


def get_data_store():
    """Return the configured data store (Postgres if configured, else local seed data)."""
    global _data_store
    if _data_store is not None:
        return _data_store

    settings = get_settings()
    if settings.database_configured:
        _data_store = PostgresDataStore(settings.database_url)
    else:
        _data_store = LocalSeedDataStore()
    return _data_store
