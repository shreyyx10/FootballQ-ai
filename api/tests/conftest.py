"""Shared pytest configuration for the FootballQ AI backend test suite.

Sets deterministic environment variables *before* any application module is
imported, so `shared.config.get_settings()` (a process-wide singleton) is
initialised with predictable, free-tier-safe values regardless of the host
environment running the tests.
"""

import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("USE_MOCK_LLM", "true")
os.environ.setdefault("ENABLE_REAL_LLM", "false")
os.environ.setdefault("ENABLE_QDRANT", "false")
os.environ.setdefault("MCP_ENABLED", "false")
os.environ.setdefault("LOG_LEVEL", "INFO")
# Disable rate limiting for tests so the in-memory limiter doesn't interfere
# with running many requests against the same "unknown" client key.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
# Ensure no real database is used during tests - always exercise the local
# seed data store fallback.
os.environ.setdefault("AZURE_SQL_CONNECTION_STRING", "")
# Allow a couple of test origins for CORS header tests.
os.environ.setdefault("ALLOWED_ORIGINS", "https://footballq-ai.vercel.app,http://localhost:3000")
