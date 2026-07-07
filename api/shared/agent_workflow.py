"""
LangGraph-inspired multi-agent workflow for /api/scout.

This module implements a graph-style workflow using modular Python
functions ("nodes"). Each node has a single responsibility and the
orchestrator (`run_scout_workflow`) wires them together in sequence,
mirroring how a LangGraph `StateGraph` would be structured.

Why not LangGraph directly?
    LangGraph's runtime dependencies and graph-execution model add
    meaningful cold-start weight to an Azure Functions Consumption-plan
    deployment, which is billed/limited by execution time and memory. To
    keep the public deployment fast, free, and dependency-light, the same
    node/edge structure is implemented with plain functions. See
    docs/AGENT_WORKFLOW.md for the LangGraph upgrade path - swapping these
    functions into `StateGraph` nodes is a drop-in change if/when desired.

Nodes (agents):
    1. classify_query        - Query Classifier
    2. stats_agent            - Stats Agent
    3. retrieve_context        - SQL RAG Retriever (rag_retriever.py)
    4. similarity_agent        - Similarity Agent (similarity.py)
    5. comparison_agent        - Comparison Agent (comparison.py)
    6. tactical_fit_agent       - Tactical Fit Agent (tactical_fit.py)
    7. recommendation_agent    - Recommendation Agent
    8. safety_agent            - Safety Agent (security.py heuristics)

No hidden chain-of-thought is ever included in the response - only the
concise `workflow_summary` list of human-readable strings.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from .comparison import build_comparison
from .database import PlayerFilters, get_data_store
from .mock_llm import (
    generate_comparison_narrative,
    generate_general_answer,
    generate_player_search_answer,
    generate_scouting_report,
    generate_similarity_explanation,
    generate_tactical_fit_summary,
)
from .rag_retriever import extract_keywords, retrieve_context
from .response_formatter import assemble_scout_response, build_supporting_statistics, clean_players
from .security import detect_prompt_injection
from .similarity import compute_similarity, similarity_result_to_dict
from .tactical_fit import compute_tactical_fit

QueryType = str  # one of the QUERY_TYPES below

QUERY_TYPES = {
    "player_search",
    "player_comparison",
    "player_similarity",
    "tactical_fit",
    "scouting_report",
    "general_question",
}


# -----------------------------------------------------------------------------
# Node 1: Query Classifier
# -----------------------------------------------------------------------------

def classify_query(query: str, players: list[dict[str, Any]], team_profiles: list[dict[str, Any]]) -> tuple[QueryType, dict[str, list[str]]]:
    """Classify a natural-language scouting query and extract entities."""
    query_lower = query.lower()
    keywords = extract_keywords(query, players, team_profiles)

    matched_players = keywords["player_names"]
    matched_teams = keywords["team_names"]

    if "scouting report" in query_lower or "scout report" in query_lower or (
        "report" in query_lower and matched_players
    ):
        return "scouting_report", keywords

    if "similar" in query_lower and (matched_players or "similar to" in query_lower):
        return "player_similarity", keywords

    if "compare" in query_lower or " vs " in query_lower or " versus " in query_lower or len(matched_players) >= 2:
        return "player_comparison", keywords

    if matched_teams and (
        "fit" in query_lower or "system" in query_lower or "style" in query_lower
        or "suit" in query_lower or keywords["styles"]
    ):
        return "tactical_fit", keywords

    if keywords["positions"] or keywords["general_keywords"] or matched_players:
        return "player_search", keywords

    return "general_question", keywords


# -----------------------------------------------------------------------------
# Node 2: Stats Agent
# -----------------------------------------------------------------------------

_AGE_UNDER_RE = re.compile(r"under\s+(\d{1,2})")
_AGE_OVER_RE = re.compile(r"over\s+(\d{1,2})")

_SORT_METRIC_HINTS = {
    "xg": "xg",
    "expected goals": "xg",
    "xag": "xag",
    "expected assists": "xag",
    "assist": "assists",
    "goal": "goals",
    "press": "pressures_per90",
    "tackl": "tackles_per90",
    "intercept": "interceptions_per90",
    "progressive": "progressive_passes_per90",
    "dribbl": "successful_takeons_per90",
    "creat": "shot_creating_actions_per90",
    "pass completion": "pass_completion_pct",
}


def _parse_search_constraints(query: str, keywords: dict[str, list[str]]) -> dict[str, Any]:
    query_lower = query.lower()
    constraints: dict[str, Any] = {
        "position": keywords["positions"][0] if keywords["positions"] else None,
        "position_group": keywords.get("position_groups", [None])[0] if keywords.get("position_groups") else None,
        "age_min": None,
        "age_max": None,
        "sort_metrics": [],
        "undervalued": "undervalued" in query_lower or "cheap" in query_lower,
    }

    if "young" in query_lower and constraints["age_max"] is None:
        constraints["age_max"] = 23

    under_match = _AGE_UNDER_RE.search(query_lower)
    if under_match:
        constraints["age_max"] = int(under_match.group(1)) - 1

    over_match = _AGE_OVER_RE.search(query_lower)
    if over_match:
        constraints["age_min"] = int(over_match.group(1)) + 1

    for hint, metric in _SORT_METRIC_HINTS.items():
        if hint in query_lower and metric not in constraints["sort_metrics"]:
            constraints["sort_metrics"].append(metric)

    return constraints


def stats_agent(query: str, keywords: dict[str, list[str]], limit: int = 5) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Retrieve and rank players relevant to a player_search query."""
    store = get_data_store()
    constraints = _parse_search_constraints(query, keywords)

    filters = PlayerFilters(
        position=constraints["position"],
        age_min=constraints["age_min"],
        age_max=constraints["age_max"],
    )
    players = store.get_players(filters)

    if not players and not constraints["position"] and constraints["position_group"]:
        # Use a fuzzy position-group match (e.g. "midfielders" -> any "*Midfielder")
        group = constraints["position_group"].lower()
        players = [
            p for p in store.get_players(PlayerFilters(age_min=constraints["age_min"], age_max=constraints["age_max"]))
            if group in (p.get("position") or "").lower()
        ]

    if not players:
        # Retry without position filter if nothing matched
        players = store.get_players(PlayerFilters(age_min=constraints["age_min"], age_max=constraints["age_max"]))

    def _f(v: Any) -> float:
        try:
            return float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    sort_metrics = constraints["sort_metrics"] or ["xg", "xag", "shot_creating_actions_per90"]

    def score(player: dict[str, Any]) -> float:
        total = sum(_f(player.get(m)) for m in sort_metrics)
        if constraints["undervalued"]:
            market_value = _f(player.get("market_value_million")) or 1.0
            total = total / market_value * 10
        return total

    players_sorted = sorted(players, key=score, reverse=True)
    return players_sorted[:limit], constraints


# -----------------------------------------------------------------------------
# Node 4: Similarity Agent
# -----------------------------------------------------------------------------

def similarity_agent(reference_player_id: str, query: str, keywords: dict[str, list[str]], top_n: int = 5):
    store = get_data_store()
    reference_player = store.get_player(reference_player_id)
    if not reference_player:
        return None, [], {}

    constraints = _parse_search_constraints(query, keywords)
    filters = PlayerFilters(
        position=constraints["position"] or reference_player.get("position"),
        age_max=constraints["age_max"],
        age_min=constraints["age_min"],
    )
    candidates = store.get_players(filters)
    if len(candidates) <= 1:
        candidates = store.get_players()

    results = compute_similarity(reference_player, candidates, top_n=top_n)
    return reference_player, results, constraints


# -----------------------------------------------------------------------------
# Node 7: Recommendation Agent + Node 8: Safety Agent + Orchestrator
# -----------------------------------------------------------------------------

def _confidence_level(data_points: int, has_context: bool) -> str:
    if data_points == 0:
        return "Low"
    if data_points >= 3 and has_context:
        return "High"
    if data_points >= 1:
        return "Medium"
    return "Low"


def run_scout_workflow(query: str) -> dict[str, Any]:
    """Run the full multi-agent workflow for a /api/scout request.

    Returns a dict matching the documented /api/scout response shape:
    answer, recommended_players, supporting_statistics,
    retrieved_context_summary, workflow_summary, confidence_level, limitations.
    """
    store = get_data_store()
    all_players = store.get_players()
    team_profiles = store.get_team_profiles()

    workflow_summary: list[str] = []
    limitations: list[str] = []

    # --- Safety Agent (pre-check) ---------------------------------------
    injection_flags = detect_prompt_injection(query)
    if injection_flags:
        limitations.append(
            "The query contained patterns associated with prompt injection or unsafe "
            "requests (e.g. attempts to reveal hidden instructions or secrets). "
            "These were ignored and only the football scouting request was processed."
        )
    workflow_summary.append("Safety agent screened the input for unsafe or out-of-scope requests.")

    # --- Query Classifier --------------------------------------------------
    query_type, keywords = classify_query(query, all_players, team_profiles)
    workflow_summary.append(f"Query classifier identified this as a '{query_type.replace('_', ' ')}' request.")

    recommended_players: list[dict[str, Any]] = []
    answer = ""
    retrieved_context_summary: list[str] = []
    tactical_notes_text = ""

    matched_player_ids = [
        p["player_id"] for p in all_players if p.get("player_name") in keywords["player_names"]
    ]

    if query_type == "player_search":
        recommended_players, constraints = stats_agent(query, keywords)
        workflow_summary.append(
            f"Stats agent filtered and ranked {len(recommended_players)} player(s) "
            f"from the sample dataset based on the requested criteria."
        )
        rag = retrieve_context(query, matched_player_ids)
        retrieved_context_summary = rag["retrieved_context_summary"]
        workflow_summary.append("SQL RAG retriever pulled supporting scouting notes where available.")
        answer = generate_player_search_answer(query, recommended_players)
        if rag["scouting_notes"]:
            extra = " ".join(
                f"{n.get('player_name')}: {n.get('profile_summary')}" for n in rag["scouting_notes"][:2]
            )
            answer += f" Additional scouting context: {extra}"

    elif query_type == "player_comparison":
        compare_ids = matched_player_ids[:5] if len(matched_player_ids) >= 2 else [p["player_id"] for p in all_players[:2]]
        players = [store.get_player(pid) for pid in compare_ids]
        players = [p for p in players if p]
        comparison = build_comparison(players)
        recommended_players = players
        workflow_summary.append(f"Comparison agent built a side-by-side comparison across {len(comparison['comparison_table'])} metrics.")
        rag = retrieve_context(query, compare_ids)
        retrieved_context_summary = rag["retrieved_context_summary"]
        workflow_summary.append("SQL RAG retriever pulled scouting notes for the compared players.")
        answer = generate_comparison_narrative(comparison)
        if rag["scouting_notes"]:
            notes_text = " ".join(
                f"{n.get('player_name')} - tactical notes: {n.get('tactical_notes')}" for n in rag["scouting_notes"][:2]
            )
            tactical_notes_text = notes_text

    elif query_type == "player_similarity":
        reference_id = matched_player_ids[0] if matched_player_ids else (all_players[0]["player_id"] if all_players else None)
        reference_player, results, constraints = similarity_agent(reference_id, query, keywords) if reference_id else (None, [], {})
        if reference_player:
            recommended_players = [r.player for r in results]
            workflow_summary.append(f"Similarity agent ranked {len(results)} candidate(s) against {reference_player.get('player_name')}.")
            rag = retrieve_context(query, [reference_player["player_id"]] + [p["player_id"] for p in recommended_players[:2]])
            retrieved_context_summary = rag["retrieved_context_summary"]
            workflow_summary.append("SQL RAG retriever pulled scouting context for the reference and top matches.")
            results_dicts = [similarity_result_to_dict(r) for r in results]
            answer = generate_similarity_explanation(reference_player, results_dicts)
        else:
            answer = "No reference player could be identified from the query. Try naming a specific player."
            limitations.append("Reference player not found in the sample dataset.")

    elif query_type == "tactical_fit":
        team_name = keywords["team_names"][0] if keywords["team_names"] else None
        team = store.get_team_profile(team_name) if team_name else None
        if not team:
            answer = "No matching team profile was found. Try one of: " + ", ".join(t["team_name"] for t in team_profiles)
            limitations.append("Team not found in the sample dataset.")
        else:
            workflow_summary.append(f"Tactical fit agent evaluated candidates against {team['team_name']}'s tactical profile.")
            if matched_player_ids:
                candidates = [store.get_player(pid) for pid in matched_player_ids]
            else:
                position = keywords["positions"][0] if keywords["positions"] else None
                position_group = keywords.get("position_groups", [None])[0] if keywords.get("position_groups") else None
                if position:
                    candidates = store.get_players(PlayerFilters(position=position))
                elif position_group:
                    candidates = [p for p in all_players if position_group.lower() in (p.get("position") or "").lower()]
                else:
                    candidates = all_players
            candidates = [c for c in candidates if c]

            scored = []
            for player in candidates:
                fit = compute_tactical_fit(player, team, all_players)
                scored.append((fit["fit_score"], player, fit))
            scored.sort(key=lambda x: x[0], reverse=True)
            top = scored[:5]
            recommended_players = [p for _, p, _ in top]

            if top:
                best_score, best_player, best_fit = top[0]
                answer = generate_tactical_fit_summary(best_player, team, best_fit)
                if len(top) > 1:
                    others = ", ".join(f"{p.get('player_name')} ({s}/100)" for s, p, _ in top[1:4])
                    answer += f" Other candidates assessed: {others}."
                tactical_notes_text = team.get("tactical_style", "")
            else:
                answer = f"No candidates were available to evaluate against {team['team_name']}."

            rag = retrieve_context(query, matched_player_ids)
            retrieved_context_summary = rag["retrieved_context_summary"] or [
                f"Team profile retrieved for {team['team_name']} ({team['formation']}, {team['possession_style']})."
            ]
            workflow_summary.append("SQL RAG retriever pulled the team's tactical profile and any related player notes.")

    elif query_type == "scouting_report":
        target_id = matched_player_ids[0] if matched_player_ids else None
        player = store.get_player(target_id) if target_id else None
        if not player:
            answer = "No matching player was found to generate a scouting report. Try naming a specific player."
            limitations.append("Player not found in the sample dataset.")
        else:
            rag = retrieve_context(query, [player["player_id"]])
            retrieved_context_summary = rag["retrieved_context_summary"]
            scouting_note = rag["scouting_notes"][0] if rag["scouting_notes"] else None
            workflow_summary.append("SQL RAG retriever pulled the scouting note and stats for the requested player.")
            report = generate_scouting_report(player, scouting_note)
            recommended_players = [player]
            answer = report["answer"]
            tactical_notes_text = report["tactical_notes"]
            limitations.extend([] if scouting_note else ["No detailed scouting note found - response based on statistics only."])
            workflow_summary.append("Recommendation agent compiled a structured scouting report.")

    else:  # general_question
        answer = generate_general_answer(query)
        retrieved_context_summary = ["No specific player or team context matched this general query."]

    # --- Recommendation Agent: assemble final narrative ---------------------
    if tactical_notes_text:
        answer = f"{answer} Tactical notes: {tactical_notes_text}"

    if not recommended_players:
        limitations.append("No specific players could be confidently recommended for this query.")

    confidence_level = _confidence_level(len(recommended_players), bool(retrieved_context_summary) and retrieved_context_summary != ["No specific player or team context matched this general query."])

    limitations.append(
        "All data is sample/demo data for a free-tier portfolio project and should not be used for real "
        "transfer or scouting decisions."
    )

    workflow_summary.append(f"Recommendation agent finalised the response with confidence level: {confidence_level}.")

    supporting_statistics = build_supporting_statistics(recommended_players) if recommended_players else []

    # Persist a lightweight log of the query (best-effort, never raises)
    try:
        store.log_scout_query(query, answer[:500])
    except Exception:  # pragma: no cover - logging must never break the request
        pass

    return assemble_scout_response(
        answer=answer,
        recommended_players=recommended_players,
        supporting_statistics=supporting_statistics,
        retrieved_context_summary=retrieved_context_summary,
        workflow_summary=workflow_summary,
        confidence_level=confidence_level,
        limitations=limitations,
    )
