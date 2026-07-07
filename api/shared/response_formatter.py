"""
Response formatting helpers shared across API endpoints.

Centralises rounding/cleaning of numeric fields and assembly of the final
/api/scout response shape so that `function_app.py` and `agent_workflow.py`
stay focused on orchestration rather than formatting details.
"""

from __future__ import annotations

from typing import Any, Optional

ROUND_2_FIELDS = {
    "xg", "xag", "shots_per90", "key_passes_per90", "progressive_passes_per90",
    "progressive_carries_per90", "successful_takeons_per90", "shot_creating_actions_per90",
    "tackles_per90", "interceptions_per90", "pressures_per90", "pass_completion_pct",
    "market_value_million",
}


def clean_player(player: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of `player` with numeric fields rounded for display."""
    cleaned = dict(player)
    for field in ROUND_2_FIELDS:
        value = cleaned.get(field)
        if isinstance(value, (int, float)):
            cleaned[field] = round(float(value), 2)
    return cleaned


def clean_players(players: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [clean_player(p) for p in players]


def build_supporting_statistics(players: list[dict[str, Any]], metrics: Optional[list[str]] = None) -> list[dict[str, Any]]:
    """Build a compact supporting-statistics block for a list of players."""
    metrics = metrics or [
        "goals", "assists", "xg", "xag", "progressive_carries_per90",
        "shot_creating_actions_per90", "pass_completion_pct", "minutes",
    ]
    stats = []
    for player in players:
        entry = {
            "player_id": player.get("player_id"),
            "player_name": player.get("player_name"),
        }
        for metric in metrics:
            value = player.get(metric)
            if isinstance(value, float):
                value = round(value, 2)
            entry[metric] = value
        stats.append(entry)
    return stats


def assemble_scout_response(
    answer: str,
    recommended_players: list[dict[str, Any]],
    supporting_statistics: list[dict[str, Any]],
    retrieved_context_summary: list[str],
    workflow_summary: list[str],
    confidence_level: str,
    limitations: list[str],
) -> dict[str, Any]:
    """Assemble the final /api/scout response in the documented shape.

    `answer` should already contain the narrative covering: direct answer,
    why players were selected, tactical notes, and the final recommendation.
    The remaining structured fields cover the rest of the required sections:
    recommended players, supporting statistics, retrieved context, risks /
    limitations, confidence level, and a short workflow summary.

    No hidden chain-of-thought is included anywhere in this response.
    """
    return {
        "answer": answer,
        "recommended_players": clean_players(recommended_players),
        "supporting_statistics": supporting_statistics,
        "retrieved_context_summary": retrieved_context_summary,
        "workflow_summary": workflow_summary,
        "confidence_level": confidence_level,
        "limitations": limitations,
    }
