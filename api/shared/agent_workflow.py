"""
LangGraph multi-agent workflow for /api/scout.

The workflow is a real LangGraph `StateGraph`: each agent is a node that
receives the shared `ScoutState` and returns a partial state update, and a
conditional edge routes the query to the right specialist agent based on
the Query Classifier's output.

Graph shape:

    safety ──► classify ──► (router by query_type)
                              ├─► player_search ────┐
                              ├─► player_comparison ─┤
                              ├─► player_similarity ─┼─► finalize ──► END
                              ├─► tactical_fit ──────┤
                              ├─► scouting_report ───┤
                              └─► general_question ──┘

If the `langgraph` package is unavailable, the same node functions run in
the same order via a small sequential fallback, so the API degrades
gracefully rather than 500ing.

The finalize node optionally rewrites the template narrative with a real
LLM (`enhance_with_llm`, e.g. a local Ollama model) when
ENABLE_REAL_LLM=true - grounded in the structured answer, never replacing
the underlying statistics.

No hidden chain-of-thought is ever included in the response - only the
concise `workflow_summary` list of human-readable strings.
"""

from __future__ import annotations

import logging
import operator
import re
from typing import Annotated, Any, Optional, TypedDict

from .comparison import build_comparison
from .database import PlayerFilters, get_data_store
from .mock_llm import (
    enhance_with_llm,
    generate_comparison_narrative,
    generate_general_answer,
    generate_player_search_answer,
    generate_scouting_report,
    generate_similarity_explanation,
    generate_tactical_fit_summary,
)
from .config import get_settings
from .rag_retriever import extract_keywords, retrieve_context
from .response_formatter import assemble_scout_response, build_supporting_statistics
from .security import detect_prompt_injection
from .similarity import compute_similarity, similarity_result_to_dict
from .tactical_fit import compute_tactical_fit

logger = logging.getLogger("footballq.agent_workflow")

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
# Shared graph state
# -----------------------------------------------------------------------------

class ScoutState(TypedDict, total=False):
    """State threaded through the LangGraph nodes.

    `workflow_summary` and `limitations` use an additive reducer so every
    node can append its own lines without clobbering earlier ones.
    """

    query: str
    all_players: list
    team_profiles: list
    query_type: str
    keywords: dict
    matched_player_ids: list
    recommended_players: list
    answer: str
    retrieved_context_summary: list
    tactical_notes_text: str
    confidence_level: str
    workflow_summary: Annotated[list, operator.add]
    limitations: Annotated[list, operator.add]
    response: dict


# -----------------------------------------------------------------------------
# Query Classifier
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
# Stats Agent helpers
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


def _confidence_level(data_points: int, has_context: bool) -> str:
    if data_points == 0:
        return "Low"
    if data_points >= 3 and has_context:
        return "High"
    if data_points >= 1:
        return "Medium"
    return "Low"


# -----------------------------------------------------------------------------
# Graph nodes. Each takes the merged ScoutState and returns a partial update.
# -----------------------------------------------------------------------------

def safety_node(state: ScoutState) -> dict:
    """Node 1: screen the input for prompt-injection / unsafe patterns."""
    update: dict = {
        "workflow_summary": ["Safety agent screened the input for unsafe or out-of-scope requests."],
        "limitations": [],
    }
    if detect_prompt_injection(state["query"]):
        update["limitations"] = [
            "The query contained patterns associated with prompt injection or unsafe "
            "requests (e.g. attempts to reveal hidden instructions or secrets). "
            "These were ignored and only the football scouting request was processed."
        ]
    return update


def classify_node(state: ScoutState) -> dict:
    """Node 2: classify the query and extract entities."""
    query_type, keywords = classify_query(state["query"], state["all_players"], state["team_profiles"])
    matched_player_ids = [
        p["player_id"] for p in state["all_players"] if p.get("player_name") in keywords["player_names"]
    ]
    return {
        "query_type": query_type,
        "keywords": keywords,
        "matched_player_ids": matched_player_ids,
        "workflow_summary": [
            f"Query classifier identified this as a '{query_type.replace('_', ' ')}' request."
        ],
    }


def route_query(state: ScoutState) -> str:
    """Conditional edge: send the state to the matching specialist node."""
    return state["query_type"]


def player_search_node(state: ScoutState) -> dict:
    query, keywords = state["query"], state["keywords"]
    recommended_players, _constraints = stats_agent(query, keywords)
    rag = retrieve_context(query, state["matched_player_ids"])
    answer = generate_player_search_answer(query, recommended_players)
    if rag["scouting_notes"]:
        extra = " ".join(
            f"{n.get('player_name')}: {n.get('profile_summary')}" for n in rag["scouting_notes"][:2]
        )
        answer += f" Additional scouting context: {extra}"
    return {
        "recommended_players": recommended_players,
        "retrieved_context_summary": rag["retrieved_context_summary"],
        "answer": answer,
        "workflow_summary": [
            f"Stats agent filtered and ranked {len(recommended_players)} player(s) "
            f"from the dataset based on the requested criteria.",
            "SQL RAG retriever pulled supporting scouting notes where available.",
        ],
    }


def player_comparison_node(state: ScoutState) -> dict:
    store = get_data_store()
    matched = state["matched_player_ids"]
    compare_ids = matched[:5] if len(matched) >= 2 else [p["player_id"] for p in state["all_players"][:2]]
    players = [store.get_player(pid) for pid in compare_ids]
    players = [p for p in players if p]
    comparison = build_comparison(players)
    rag = retrieve_context(state["query"], compare_ids)
    update: dict = {
        "recommended_players": players,
        "retrieved_context_summary": rag["retrieved_context_summary"],
        "answer": generate_comparison_narrative(comparison),
        "workflow_summary": [
            f"Comparison agent built a side-by-side comparison across {len(comparison['comparison_table'])} metrics.",
            "SQL RAG retriever pulled scouting notes for the compared players.",
        ],
    }
    if rag["scouting_notes"]:
        update["tactical_notes_text"] = " ".join(
            f"{n.get('player_name')} - tactical notes: {n.get('tactical_notes')}" for n in rag["scouting_notes"][:2]
        )
    return update


def player_similarity_node(state: ScoutState) -> dict:
    matched = state["matched_player_ids"]
    all_players = state["all_players"]
    reference_id = matched[0] if matched else (all_players[0]["player_id"] if all_players else None)
    reference_player, results, _constraints = (
        similarity_agent(reference_id, state["query"], state["keywords"]) if reference_id else (None, [], {})
    )
    if not reference_player:
        return {
            "answer": "No reference player could be identified from the query. Try naming a specific player.",
            "limitations": ["Reference player not found in the dataset."],
        }

    recommended_players = [r.player for r in results]
    rag = retrieve_context(
        state["query"],
        [reference_player["player_id"]] + [p["player_id"] for p in recommended_players[:2]],
    )
    results_dicts = [similarity_result_to_dict(r) for r in results]
    return {
        "recommended_players": recommended_players,
        "retrieved_context_summary": rag["retrieved_context_summary"],
        "answer": generate_similarity_explanation(reference_player, results_dicts),
        "workflow_summary": [
            f"Similarity agent ranked {len(results)} candidate(s) against {reference_player.get('player_name')}.",
            "SQL RAG retriever pulled scouting context for the reference and top matches.",
        ],
    }


def tactical_fit_node(state: ScoutState) -> dict:
    store = get_data_store()
    keywords, all_players = state["keywords"], state["all_players"]
    team_name = keywords["team_names"][0] if keywords["team_names"] else None
    team = store.get_team_profile(team_name) if team_name else None
    if not team:
        return {
            "answer": "No matching team profile was found. Try one of: "
            + ", ".join(t["team_name"] for t in state["team_profiles"]),
            "limitations": ["Team not found in the dataset."],
        }

    matched = state["matched_player_ids"]
    if matched:
        candidates = [store.get_player(pid) for pid in matched]
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

    update: dict = {
        "recommended_players": [p for _, p, _ in top],
        "workflow_summary": [
            f"Tactical fit agent evaluated candidates against {team['team_name']}'s tactical profile.",
            "SQL RAG retriever pulled the team's tactical profile and any related player notes.",
        ],
    }

    if top:
        _best_score, best_player, best_fit = top[0]
        answer = generate_tactical_fit_summary(best_player, team, best_fit)
        if len(top) > 1:
            others = ", ".join(f"{p.get('player_name')} ({s}/100)" for s, p, _ in top[1:4])
            answer += f" Other candidates assessed: {others}."
        update["answer"] = answer
        update["tactical_notes_text"] = team.get("tactical_style", "")
    else:
        update["answer"] = f"No candidates were available to evaluate against {team['team_name']}."

    rag = retrieve_context(state["query"], matched)
    update["retrieved_context_summary"] = rag["retrieved_context_summary"] or [
        f"Team profile retrieved for {team['team_name']} ({team['formation']}, {team['possession_style']})."
    ]
    return update


def scouting_report_node(state: ScoutState) -> dict:
    store = get_data_store()
    matched = state["matched_player_ids"]
    target_id = matched[0] if matched else None
    player = store.get_player(target_id) if target_id else None
    if not player:
        return {
            "answer": "No matching player was found to generate a scouting report. Try naming a specific player.",
            "limitations": ["Player not found in the dataset."],
        }

    rag = retrieve_context(state["query"], [player["player_id"]])
    scouting_note = rag["scouting_notes"][0] if rag["scouting_notes"] else None
    report = generate_scouting_report(player, scouting_note)
    update: dict = {
        "recommended_players": [player],
        "retrieved_context_summary": rag["retrieved_context_summary"],
        "answer": report["answer"],
        "tactical_notes_text": report["tactical_notes"],
        "workflow_summary": [
            "SQL RAG retriever pulled the scouting note and stats for the requested player.",
            "Recommendation agent compiled a structured scouting report.",
        ],
    }
    if not scouting_note:
        update["limitations"] = ["No detailed scouting note found - response based on statistics only."]
    return update


def general_question_node(state: ScoutState) -> dict:
    return {
        "answer": generate_general_answer(state["query"]),
        "retrieved_context_summary": ["No specific player or team context matched this general query."],
    }


def finalize_node(state: ScoutState) -> dict:
    """Recommendation agent: assemble narrative, confidence, and optionally
    rewrite the template answer with a real LLM (grounded, never inventing
    statistics)."""
    settings = get_settings()
    answer = state.get("answer", "")
    tactical_notes_text = state.get("tactical_notes_text", "")
    recommended_players = state.get("recommended_players", [])
    retrieved_context_summary = state.get("retrieved_context_summary", [])

    if tactical_notes_text:
        answer = f"{answer} Tactical notes: {tactical_notes_text}"

    update: dict = {"limitations": [], "workflow_summary": []}
    if not recommended_players:
        update["limitations"].append("No specific players could be confidently recommended for this query.")

    confidence_level = _confidence_level(
        len(recommended_players),
        bool(retrieved_context_summary)
        and retrieved_context_summary != ["No specific player or team context matched this general query."],
    )

    if settings.enable_real_llm:
        stats_lines = "; ".join(
            f"{p.get('player_name')} ({p.get('club')}): {p.get('goals')} goals, "
            f"{p.get('assists')} assists, xG {p.get('xg')}, {p.get('minutes')} min"
            for p in recommended_players[:5]
        )
        enhanced = enhance_with_llm(
            system_prompt=(
                "You are a professional football scout writing for a scouting platform. "
                "Rewrite the draft answer to be natural and engaging, in 2-4 sentences. "
                "Use ONLY the facts and statistics provided - never invent numbers, "
                "players, or claims. Keep every statistic exactly as given."
            ),
            user_prompt=(
                f"Question: {state['query']}\n\nDraft answer: {answer}\n\n"
                f"Player statistics: {stats_lines or 'none'}"
            ),
            fallback_text=answer,
        )
        if enhanced != answer:
            answer = enhanced
            update["workflow_summary"].append(
                f"LLM narrative agent ({settings.llm_model}) rewrote the final answer from the structured draft."
            )

    update["limitations"].append(
        "All data is sample/demo data for a free-tier portfolio project and should not be used for real "
        "transfer or scouting decisions."
    )
    update["workflow_summary"].append(
        f"Recommendation agent finalised the response with confidence level: {confidence_level}."
    )

    return {**update, "answer": answer, "confidence_level": confidence_level}


# -----------------------------------------------------------------------------
# Graph construction
# -----------------------------------------------------------------------------

_BRANCH_NODES = {
    "player_search": player_search_node,
    "player_comparison": player_comparison_node,
    "player_similarity": player_similarity_node,
    "tactical_fit": tactical_fit_node,
    "scouting_report": scouting_report_node,
    "general_question": general_question_node,
}

_compiled_graph = None


def _build_graph():
    """Build and compile the LangGraph StateGraph (cached per process)."""
    global _compiled_graph
    if _compiled_graph is not None:
        return _compiled_graph

    from langgraph.graph import END, StateGraph

    graph = StateGraph(ScoutState)
    graph.add_node("safety", safety_node)
    graph.add_node("classify", classify_node)
    for name, fn in _BRANCH_NODES.items():
        graph.add_node(name, fn)
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("safety")
    graph.add_edge("safety", "classify")
    graph.add_conditional_edges("classify", route_query, {name: name for name in _BRANCH_NODES})
    for name in _BRANCH_NODES:
        graph.add_edge(name, "finalize")
    graph.add_edge("finalize", END)

    _compiled_graph = graph.compile()
    return _compiled_graph


def _run_sequential(state: dict) -> dict:
    """Fallback executor mirroring the graph when langgraph isn't installed."""
    def apply(update: dict) -> None:
        for key, value in update.items():
            if key in ("workflow_summary", "limitations"):
                state[key] = state.get(key, []) + value
            else:
                state[key] = value

    apply(safety_node(state))  # type: ignore[arg-type]
    apply(classify_node(state))  # type: ignore[arg-type]
    apply(_BRANCH_NODES[route_query(state)](state))  # type: ignore[index,arg-type]
    apply(finalize_node(state))  # type: ignore[arg-type]
    return state


def run_scout_workflow(query: str) -> dict[str, Any]:
    """Run the full multi-agent workflow for a /api/scout request.

    Returns a dict matching the documented /api/scout response shape:
    answer, recommended_players, supporting_statistics,
    retrieved_context_summary, workflow_summary, confidence_level, limitations.
    """
    store = get_data_store()
    initial_state: dict = {
        "query": query,
        "all_players": store.get_players(),
        "team_profiles": store.get_team_profiles(),
        "workflow_summary": [],
        "limitations": [],
        "recommended_players": [],
        "retrieved_context_summary": [],
        "answer": "",
        "tactical_notes_text": "",
    }

    try:
        final_state = _build_graph().invoke(initial_state)
    except ImportError:
        logger.warning("langgraph not installed; running sequential fallback workflow")
        final_state = _run_sequential(initial_state)

    recommended_players = final_state.get("recommended_players", [])
    supporting_statistics = build_supporting_statistics(recommended_players) if recommended_players else []

    # Persist a lightweight log of the query (best-effort, never raises)
    try:
        store.log_scout_query(query, final_state.get("answer", "")[:500])
    except Exception:  # pragma: no cover - logging must never break the request
        pass

    return assemble_scout_response(
        answer=final_state.get("answer", ""),
        recommended_players=recommended_players,
        supporting_statistics=supporting_statistics,
        retrieved_context_summary=final_state.get("retrieved_context_summary", []),
        workflow_summary=final_state.get("workflow_summary", []),
        confidence_level=final_state.get("confidence_level", "Low"),
        limitations=final_state.get("limitations", []),
    )
