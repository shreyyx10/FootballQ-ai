"""
SQL-backed RAG (Retrieval-Augmented Generation) retriever.

Default mode (always available, zero cost):
    - Extracts keywords from a natural-language query (player names, team
      names, positions, tactical/style terms).
    - Uses weighted keyword scoring over `ScoutingNotes` and `TeamProfiles`
      (via the configured DataStore - Azure SQL or local seed data) to
      retrieve the most relevant context.

Optional mode (ENABLE_QDRANT=true):
    - If a Qdrant client and credentials are configured, semantic search
      can be layered on top. If Qdrant is not configured, not installed, or
      the call fails for any reason, retrieval silently falls back to the
      SQL keyword-based method above. The app must never crash because of
      a missing/optional Qdrant dependency.

No paid embeddings or vector databases are required for the app to function.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from .config import get_settings
from .database import get_data_store

logger = logging.getLogger("footballq.rag")

# Generic plural/positional terms mapped to a substring that appears in the
# `position` field of one or more specific positions (used for fuzzy
# position-group matching, e.g. "midfielders" -> any "*Midfielder" position).
GENERIC_POSITION_GROUPS: dict[str, str] = {
    "midfielders": "Midfielder",
    "midfielder": "Midfielder",
    "wingers": "Winger",
    "winger": "Winger",
    "strikers": "Striker",
    "striker": "Striker",
    "forwards": "Striker",
    "forward": "Striker",
    "full-backs": "Full-back",
    "fullbacks": "Full-back",
    "full-back": "Full-back",
    "fullback": "Full-back",
    "centre-backs": "Centre-back",
    "center-backs": "Centre-back",
    "centre-back": "Centre-back",
    "center-back": "Centre-back",
    "defenders": "Centre-back",
    "defender": "Centre-back",
}

# Common football tactical/style terms that help match team profiles
STYLE_KEYWORDS = [
    "possession", "pressing", "press", "counter", "counter-attack", "transition",
    "high line", "low block", "tiki-taka", "direct", "vertical", "overlap",
    "inverted", "wing-back", "build-up", "tempo",
]

# Stopwords to exclude from keyword extraction
STOPWORDS = {
    "find", "me", "a", "an", "the", "for", "to", "of", "and", "or", "with",
    "is", "are", "who", "which", "best", "good", "young", "old", "under",
    "over", "similar", "compare", "vs", "versus", "than", "explain", "why",
    "generate", "report", "scouting", "player", "players", "team", "system",
    "fit", "tactical", "high", "low", "show", "give", "list", "top", "in",
    "on", "at", "this", "that", "these", "those", "be", "do", "does", "i",
    "want", "would", "like", "please", "can", "you", "tell", "about", "based",
}


def extract_keywords(query: str, players: list[dict[str, Any]], team_profiles: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Extract player names, team names, positions and style keywords from a query."""
    query_lower = query.lower()

    matched_players = []
    for p in players:
        name = p.get("player_name") or ""
        if not name:
            continue
        last_name = name.split()[-1].lower()
        if name.lower() in query_lower or (len(last_name) > 3 and last_name in query_lower):
            matched_players.append(p)

    matched_teams = [
        t for t in team_profiles
        if t.get("team_name") and t["team_name"].lower() in query_lower
    ]

    positions = sorted({p.get("position") for p in players if p.get("position")})
    matched_positions = [pos for pos in positions if pos.lower() in query_lower or pos.lower().rstrip("s") in query_lower]
    # handle plurals like "wingers", "strikers", "midfielders"
    for pos in positions:
        pos_lower = pos.lower()
        if pos_lower + "s" in query_lower and pos not in matched_positions:
            matched_positions.append(pos)

    # Generic position-group terms (e.g. "midfielders" should match any
    # position containing "Midfielder" even though no single `position`
    # value equals "Midfielder").
    matched_position_groups: list[str] = []
    for group_term, group_fragment in GENERIC_POSITION_GROUPS.items():
        if group_term in query_lower and group_fragment not in matched_position_groups:
            matched_position_groups.append(group_fragment)

    matched_styles = [kw for kw in STYLE_KEYWORDS if kw in query_lower]

    # General keyword tokens (for fallback search)
    tokens = re.findall(r"[a-zA-Z]+", query_lower)
    general_keywords = [t for t in tokens if t not in STOPWORDS and len(t) > 2]

    return {
        "player_names": [p["player_name"] for p in matched_players],
        "team_names": [t["team_name"] for t in matched_teams],
        "positions": matched_positions,
        "position_groups": matched_position_groups,
        "styles": matched_styles,
        "general_keywords": general_keywords,
    }


def _qdrant_search(query: str) -> list[dict[str, Any]] | None:
    """Optional Qdrant semantic search. Returns None if unavailable/disabled.

    This function must never raise - any failure results in `None` so the
    caller falls back to SQL keyword retrieval.
    """
    settings = get_settings()
    if not settings.enable_qdrant or not settings.qdrant_url:
        return None

    try:
        from qdrant_client import QdrantClient  # type: ignore

        client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None, timeout=5)
        # Placeholder: a real implementation would embed `query` and search a
        # pre-populated collection. Since no paid embedding model is required
        # by default, this path is inert unless a future embedding provider
        # is configured.
        _ = client
        logger.info("Qdrant client initialised but semantic search is not configured - using SQL retrieval")
        return None
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.warning("Qdrant search unavailable, falling back to SQL retrieval: %s", type(exc).__name__)
        return None


def retrieve_context(query: str, reference_player_ids: list[str] | None = None) -> dict[str, Any]:
    """Retrieve scouting notes and team profiles relevant to `query`.

    Returns a dict with:
        - scouting_notes: list of matched ScoutingNotes records
        - team_profiles: list of matched TeamProfiles records
        - retrieved_context_summary: list[str] human-readable summary lines
        - method: "qdrant" or "sql_keyword"
    """
    store = get_data_store()
    players = store.get_players()
    team_profiles_all = store.get_team_profiles()

    keywords = extract_keywords(query, players, team_profiles_all)

    # Optional semantic layer (no-op unless configured)
    qdrant_result = _qdrant_search(query)
    method = "qdrant" if qdrant_result is not None else "sql_keyword"

    matched_player_ids: list[str] = []
    if reference_player_ids:
        matched_player_ids.extend(reference_player_ids)
    for name in keywords["player_names"]:
        for p in players:
            if p.get("player_name") == name and p["player_id"] not in matched_player_ids:
                matched_player_ids.append(p["player_id"])

    scouting_notes: list[dict[str, Any]] = []
    if matched_player_ids:
        scouting_notes.extend(store.get_scouting_notes(matched_player_ids))

    # Always supplement with keyword search to catch positional/style queries
    search_terms = keywords["player_names"] + keywords["positions"] + keywords["general_keywords"]
    if search_terms:
        extra_notes = store.search_scouting_notes(search_terms, limit=5)
        for note in extra_notes:
            if note.get("player_id") not in {n.get("player_id") for n in scouting_notes}:
                scouting_notes.append(note)

    scouting_notes = scouting_notes[:5]

    team_profiles: list[dict[str, Any]] = []
    if keywords["team_names"]:
        for name in keywords["team_names"]:
            profile = store.get_team_profile(name)
            if profile:
                team_profiles.append(profile)
    else:
        style_and_general = keywords["styles"] + keywords["general_keywords"]
        if style_and_general:
            team_profiles = store.search_team_profiles(style_and_general, limit=2)

    summary_lines: list[str] = []
    for note in scouting_notes:
        summary_lines.append(f"Scouting note retrieved for {note.get('player_name')}.")
    for team in team_profiles:
        summary_lines.append(f"Team profile retrieved for {team.get('team_name')} ({team.get('formation')}, {team.get('possession_style')}).")
    if not summary_lines:
        summary_lines.append("No closely matching scouting notes or team profiles found - using player statistics only.")

    return {
        "scouting_notes": scouting_notes,
        "team_profiles": team_profiles,
        "retrieved_context_summary": summary_lines,
        "method": method,
        "keywords": keywords,
    }
