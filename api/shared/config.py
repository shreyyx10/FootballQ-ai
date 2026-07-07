"""
Centralised configuration for the FootballQ AI Azure Functions API.

All configuration is read from environment variables (Azure Functions
"Application Settings" in production, or a local `local.settings.json` /
`.env` for local development). No secrets are hardcoded.

This module never logs or returns the raw value of secret settings such as
AZURE_SQL_CONNECTION_STRING or OPENAI_API_KEY.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _get_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_list(name: str, default: list[str] | None = None) -> list[str]:
    raw = os.environ.get(name)
    if not raw:
        return default or []
    return [item.strip() for item in raw.split(",") if item.strip()]


def _get_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    """Application settings loaded once per process."""

    environment: str = field(default_factory=lambda: os.environ.get("ENVIRONMENT", "production"))

    # Database (PostgreSQL - Neon/Supabase free tier). Never logged or
    # returned to clients. AZURE_SQL_CONNECTION_STRING is accepted as a
    # legacy fallback name from the original Azure SQL design.
    database_url: str = field(
        default_factory=lambda: os.environ.get("DATABASE_URL", "")
        or os.environ.get("AZURE_SQL_CONNECTION_STRING", "")
    )

    # CORS allowlist
    allowed_origins: list[str] = field(
        default_factory=lambda: _get_list(
            "ALLOWED_ORIGINS", ["https://footballq-ai.vercel.app"]
        )
    )

    # LLM mode
    use_mock_llm: bool = field(default_factory=lambda: _get_bool("USE_MOCK_LLM", True))
    enable_real_llm: bool = field(default_factory=lambda: _get_bool("ENABLE_REAL_LLM", False))
    openai_api_key: str = field(default_factory=lambda: os.environ.get("OPENAI_API_KEY", ""))
    llm_model: str = field(default_factory=lambda: os.environ.get("LLM_MODEL", "gpt-4o-mini"))

    # Optional Qdrant vector search
    enable_qdrant: bool = field(default_factory=lambda: _get_bool("ENABLE_QDRANT", False))
    qdrant_url: str = field(default_factory=lambda: os.environ.get("QDRANT_URL", ""))
    qdrant_api_key: str = field(default_factory=lambda: os.environ.get("QDRANT_API_KEY", ""))

    # Rate limiting & logging
    rate_limit_enabled: bool = field(default_factory=lambda: _get_bool("RATE_LIMIT_ENABLED", True))
    rate_limit_max_requests: int = field(default_factory=lambda: _get_int("RATE_LIMIT_MAX_REQUESTS", 30))
    rate_limit_window_seconds: int = field(default_factory=lambda: _get_int("RATE_LIMIT_WINDOW_SECONDS", 60))
    log_level: str = field(default_factory=lambda: os.environ.get("LOG_LEVEL", "INFO"))

    # Optional MCP module
    mcp_enabled: bool = field(default_factory=lambda: _get_bool("MCP_ENABLED", False))

    # Optional FBref data pipeline (see docs/FBREF_PIPELINE.md). Disabled by
    # default - requires AZURE_SQL_CONNECTION_STRING to be configured, and is
    # opt-in to keep the default deployment a pure read-only demo.
    fbref_pipeline_enabled: bool = field(default_factory=lambda: _get_bool("FBREF_PIPELINE_ENABLED", False))
    # "wayback" (default): fetch FBref pages from web.archive.org snapshots.
    # FBref/Cloudflare blocks all non-browser clients (HTTP 403) as of 2026,
    # so direct fetching no longer works from scripts. "direct" keeps the old
    # behaviour in case FBref relaxes this.
    fbref_fetch_mode: str = field(
        default_factory=lambda: os.environ.get("FBREF_FETCH_MODE", "wayback").strip().lower()
    )
    # Wayback mode: snapshots older than this trigger a Save Page Now
    # request so the Archive captures a fresh copy of the FBref page.
    fbref_wayback_max_snapshot_age_days: int = field(
        default_factory=lambda: _get_int("FBREF_WAYBACK_MAX_SNAPSHOT_AGE_DAYS", 2)
    )
    fbref_season: str = field(default_factory=lambda: os.environ.get("FBREF_SEASON", "2025-2026"))
    fbref_request_delay_seconds: float = field(
        default_factory=lambda: _get_float("FBREF_REQUEST_DELAY_SECONDS", 6.0)
    )
    fbref_user_agent: str = field(
        default_factory=lambda: os.environ.get(
            "FBREF_USER_AGENT",
            "FootballQAI-Pipeline/1.0 (+https://github.com/; portfolio project, low-volume daily scrape)",
        )
    )
    fbref_matchlog_teams_per_run: int = field(
        default_factory=lambda: _get_int("FBREF_MATCHLOG_TEAMS_PER_RUN", 2)
    )
    fbref_extra_leagues_per_run: int = field(
        default_factory=lambda: _get_int("FBREF_EXTRA_LEAGUES_PER_RUN", 1)
    )

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def database_configured(self) -> bool:
        """True if a database connection string has been provided."""
        return bool(self.database_url.strip())

    @property
    def azure_sql_connection_string(self) -> str:
        """Legacy alias for database_url (pre-Postgres migration name)."""
        return self.database_url


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return a cached Settings instance (singleton per process)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
