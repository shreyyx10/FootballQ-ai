"""
Optional MCP (Model Context Protocol) tool stubs for FootballQ AI.

These functions wrap the same business logic used by the public API
(`function_app.py`) so there is a single source of truth - no logic is
duplicated. They are NOT required for the public website to function and
are not invoked by any deployed Azure Function by default.

MCP_ENABLED=false by default. If a future MCP server is wired up (see
docs/MCP_OPTIONAL.md), it can import and call these functions directly.

Security notes:
- These tools only call read-oriented service functions (database reads,
  similarity/comparison/tactical-fit/scouting computations).
- No tool here executes shell commands, reads/writes arbitrary files, or
  exposes environment variables / connection strings.
- All inputs should still be validated by the MCP host using the same
  Pydantic schemas in `shared/schemas.py` before calling these functions.
"""

from __future__ import annotations

from typing import Any, Optional

from .agent_workflow import run_scout_workflow, similarity_agent
from .comparison import build_comparison
from .database import PlayerFilters, get_data_store
from .mock_llm import generate_scouting_report
from .rag_retriever import retrieve_context
from .similarity import similarity_result_to_dict
from .tactical_fit import compute_tactical_fit


def search_players(
    position: Optional[str] = None,
    league: Optional[str] = None,
    club: Optional[str] = None,
    age_min: Optional[int] = None,
    age_max: Optional[int] = None,
    minutes_min: Optional[int] = None,
) -> list[dict[str, Any]]:
    """MCP tool: search players by structured filters (mirrors GET /api/players)."""
    store = get_data_store()
    filters = PlayerFilters(
        position=position, league=league, club=club,
        age_min=age_min, age_max=age_max, minutes_min=minutes_min,
    )
    return store.get_players(filters)


def get_player_profile(player_id: str) -> Optional[dict[str, Any]]:
    """MCP tool: fetch a single player's full statistical profile."""
    store = get_data_store()
    return store.get_player(player_id)


def compare_players(player_ids: list[str]) -> dict[str, Any]:
    """MCP tool: compare 2-5 players (mirrors POST /api/compare)."""
    store = get_data_store()
    players = [store.get_player(pid) for pid in player_ids]
    players = [p for p in players if p]
    if len(players) < 2:
        return {"error": "At least two valid player_ids are required."}
    return build_comparison(players)


def find_similar_players(reference_player_id: str, position: Optional[str] = None, age_max: Optional[int] = None, top_n: int = 5) -> dict[str, Any]:
    """MCP tool: find statistically similar players (mirrors POST /api/similarity)."""
    query_hint = ""
    if position:
        query_hint += f" position {position}"
    if age_max:
        query_hint += f" under {age_max + 1}"

    reference_player, results, _ = similarity_agent(reference_player_id, query_hint, {"positions": [position] if position else [], "general_keywords": []}, top_n=top_n)
    if not reference_player:
        return {"error": "reference_player_id not found"}

    return {
        "reference_player": reference_player,
        "similar_players": [similarity_result_to_dict(r) for r in results],
        "method": "weighted_euclidean_normalised",
    }


def tactical_fit_analysis(player_id: str, team_name: str) -> dict[str, Any]:
    """MCP tool: evaluate tactical fit (mirrors POST /api/tactical-fit)."""
    store = get_data_store()
    player = store.get_player(player_id)
    team = store.get_team_profile(team_name)
    if not player or not team:
        return {"error": "player_id or team_name not found"}

    all_players = store.get_players()
    fit = compute_tactical_fit(player, team, all_players)
    return {"player": player, "team": team, **fit}


def generate_scouting_report_tool(player_id: str) -> dict[str, Any]:
    """MCP tool: generate a scouting report for a player (mirrors a scouting_report /api/scout query)."""
    store = get_data_store()
    player = store.get_player(player_id)
    if not player:
        return {"error": "player_id not found"}

    rag = retrieve_context(player.get("player_name", ""), [player_id])
    scouting_note = rag["scouting_notes"][0] if rag["scouting_notes"] else None
    return generate_scouting_report(player, scouting_note)


def scout_query(query: str) -> dict[str, Any]:
    """MCP tool: run a full natural-language scouting query (mirrors POST /api/scout)."""
    return run_scout_workflow(query)
