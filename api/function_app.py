"""
FootballQ AI - Azure Functions Python API (HTTP-triggered, Consumption plan).

Endpoints:
    GET  /api/health
    GET  /api/players
    GET  /api/players/{player_id}
    POST /api/compare
    POST /api/similarity
    POST /api/tactical-fit
    POST /api/scout

All endpoints:
    - Validate input with Pydantic (shared/schemas.py).
    - Apply CORS based on ALLOWED_ORIGINS (shared/security.py).
    - Return safe JSON error responses - never raw stack traces.
    - Apply best-effort rate limiting (shared/security.py).
    - Log requests via the configured data store (Azure SQL or no-op locally).
"""

from __future__ import annotations

import json
import logging

import azure.functions as func
from pydantic import ValidationError

from shared.comparison import build_comparison
from shared.config import get_settings
from shared.database import PlayerFilters, get_data_store
from shared.agent_workflow import run_scout_workflow
from shared.response_formatter import clean_player, clean_players
from shared.schemas import (
    ComparePlayersRequest,
    PlayerQueryParams,
    ScoutQueryRequest,
    SimilarityRequest,
    TacticalFitRequest,
)
from shared.security import (
    error_response,
    is_rate_limited,
    json_response,
    log_safe_exception,
)
from shared.similarity import similarity_result_to_dict
from shared.tactical_fit import compute_tactical_fit

logging.basicConfig(level=getattr(logging, get_settings().log_level.upper(), logging.INFO))
logger = logging.getLogger("footballq.api")

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


def _origin(req: func.HttpRequest) -> str | None:
    return req.headers.get("Origin")


def _client_key(req: func.HttpRequest) -> str:
    # Best-effort client identifier for in-memory rate limiting.
    return req.headers.get("X-Forwarded-For", "unknown").split(",")[0].strip()


def _rate_limit_check(req: func.HttpRequest) -> func.HttpResponse | None:
    settings = get_settings()
    if settings.rate_limit_enabled and is_rate_limited(_client_key(req)):
        body, status, headers = error_response(
            "Too many requests. Please slow down and try again shortly.",
            status_code=429,
            origin=_origin(req),
            code="rate_limited",
        )
        return func.HttpResponse(body, status_code=status, headers=headers)
    return None


def _log_call(endpoint: str, status_code: int, error_summary: str | None = None) -> None:
    try:
        get_data_store().log_api_call(endpoint, status_code, error_summary)
    except Exception:  # pragma: no cover - logging must never break a request
        pass


def _options_response(req: func.HttpRequest) -> func.HttpResponse:
    body, status, headers = json_response({}, status_code=204, origin=_origin(req))
    return func.HttpResponse(status_code=status, headers=headers)


# -----------------------------------------------------------------------------
# GET /api/health
# -----------------------------------------------------------------------------

@app.route(route="health", methods=["GET", "OPTIONS"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _options_response(req)

    body, status, headers = json_response(
        {"status": "ok", "service": "FootballQ AI API", "mode": "free-demo"},
        origin=_origin(req),
    )
    _log_call("/api/health", status)
    return func.HttpResponse(body, status_code=status, headers=headers)


# -----------------------------------------------------------------------------
# GET /api/players, GET /api/players/{player_id}
# -----------------------------------------------------------------------------

@app.route(route="players", methods=["GET", "OPTIONS"])
def list_players(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _options_response(req)

    if (limited := _rate_limit_check(req)) is not None:
        return limited

    try:
        params = req.params
        age_min = params.get("age_min")
        age_max = params.get("age_max")
        minutes_min = params.get("minutes_min")

        query_params = PlayerQueryParams(
            position=params.get("position"),
            league=params.get("league"),
            club=params.get("club"),
            age_min=int(age_min) if age_min else None,
            age_max=int(age_max) if age_max else None,
            minutes_min=int(minutes_min) if minutes_min else None,
        )
    except (ValidationError, ValueError) as exc:
        log_safe_exception("list_players.validation", exc)
        body, status, headers = error_response("Invalid query parameters.", status_code=400, origin=_origin(req), code="validation_error")
        _log_call("/api/players", status, "validation_error")
        return func.HttpResponse(body, status_code=status, headers=headers)

    try:
        store = get_data_store()
        filters = PlayerFilters(
            position=query_params.position,
            league=query_params.league,
            club=query_params.club,
            age_min=query_params.age_min,
            age_max=query_params.age_max,
            minutes_min=query_params.minutes_min,
        )
        players = store.get_players(filters)
        body, status, headers = json_response({"players": clean_players(players), "count": len(players)}, origin=_origin(req))
        _log_call("/api/players", status)
        return func.HttpResponse(body, status_code=status, headers=headers)
    except Exception as exc:
        log_safe_exception("list_players", exc)
        body, status, headers = error_response("Unable to retrieve players right now.", status_code=500, origin=_origin(req), code="internal_error")
        _log_call("/api/players", status, "internal_error")
        return func.HttpResponse(body, status_code=status, headers=headers)


@app.route(route="players/{player_id}", methods=["GET", "OPTIONS"])
def get_player(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _options_response(req)

    if (limited := _rate_limit_check(req)) is not None:
        return limited

    player_id = req.route_params.get("player_id", "")

    from shared.security import is_valid_player_id

    if not is_valid_player_id(player_id):
        body, status, headers = error_response("Invalid player_id.", status_code=400, origin=_origin(req), code="validation_error")
        _log_call("/api/players/{player_id}", status, "validation_error")
        return func.HttpResponse(body, status_code=status, headers=headers)

    try:
        store = get_data_store()
        player = store.get_player(player_id)
        if not player:
            body, status, headers = error_response("Player not found.", status_code=404, origin=_origin(req), code="not_found")
            _log_call("/api/players/{player_id}", status, "not_found")
            return func.HttpResponse(body, status_code=status, headers=headers)

        body, status, headers = json_response({"player": clean_player(player)}, origin=_origin(req))
        _log_call("/api/players/{player_id}", status)
        return func.HttpResponse(body, status_code=status, headers=headers)
    except Exception as exc:
        log_safe_exception("get_player", exc)
        body, status, headers = error_response("Unable to retrieve player right now.", status_code=500, origin=_origin(req), code="internal_error")
        _log_call("/api/players/{player_id}", status, "internal_error")
        return func.HttpResponse(body, status_code=status, headers=headers)


# -----------------------------------------------------------------------------
# POST /api/compare
# -----------------------------------------------------------------------------

@app.route(route="compare", methods=["POST", "OPTIONS"])
def compare_players_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _options_response(req)

    if (limited := _rate_limit_check(req)) is not None:
        return limited

    try:
        payload = req.get_json()
        request_model = ComparePlayersRequest(**payload)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        log_safe_exception("compare.validation", exc)
        body, status, headers = error_response("Invalid request body. Expected 2-5 player_ids.", status_code=400, origin=_origin(req), code="validation_error")
        _log_call("/api/compare", status, "validation_error")
        return func.HttpResponse(body, status_code=status, headers=headers)

    try:
        store = get_data_store()
        players = [store.get_player(pid) for pid in request_model.player_ids]
        missing = [pid for pid, p in zip(request_model.player_ids, players) if p is None]
        if missing:
            body, status, headers = error_response(f"Unknown player_id(s): {', '.join(missing)}", status_code=404, origin=_origin(req), code="not_found")
            _log_call("/api/compare", status, "not_found")
            return func.HttpResponse(body, status_code=status, headers=headers)

        comparison = build_comparison([p for p in players if p])
        comparison["players"] = clean_players(comparison["players"])
        body, status, headers = json_response(comparison, origin=_origin(req))
        _log_call("/api/compare", status)
        return func.HttpResponse(body, status_code=status, headers=headers)
    except Exception as exc:
        log_safe_exception("compare", exc)
        body, status, headers = error_response("Unable to compare players right now.", status_code=500, origin=_origin(req), code="internal_error")
        _log_call("/api/compare", status, "internal_error")
        return func.HttpResponse(body, status_code=status, headers=headers)


# -----------------------------------------------------------------------------
# POST /api/similarity
# -----------------------------------------------------------------------------

@app.route(route="similarity", methods=["POST", "OPTIONS"])
def similarity_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _options_response(req)

    if (limited := _rate_limit_check(req)) is not None:
        return limited

    try:
        payload = req.get_json()
        request_model = SimilarityRequest(**payload)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        log_safe_exception("similarity.validation", exc)
        body, status, headers = error_response("Invalid request body.", status_code=400, origin=_origin(req), code="validation_error")
        _log_call("/api/similarity", status, "validation_error")
        return func.HttpResponse(body, status_code=status, headers=headers)

    try:
        store = get_data_store()
        reference_player = store.get_player(request_model.reference_player_id)
        if not reference_player:
            body, status, headers = error_response("reference_player_id not found.", status_code=404, origin=_origin(req), code="not_found")
            _log_call("/api/similarity", status, "not_found")
            return func.HttpResponse(body, status_code=status, headers=headers)

        filters = request_model.filters
        player_filters = PlayerFilters(
            position=(filters.position if filters else None) or reference_player.get("position"),
            age_min=filters.age_min if filters else None,
            age_max=filters.age_max if filters else None,
            minutes_min=filters.minutes_min if filters else None,
            league=filters.league if filters else None,
        )
        candidates = store.get_players(player_filters)
        if len(candidates) <= 1:
            candidates = store.get_players()

        from shared.similarity import compute_similarity

        results = compute_similarity(reference_player, candidates, top_n=request_model.top_n)

        response = {
            "reference_player": clean_player(reference_player),
            "similar_players": [
                {**similarity_result_to_dict(r), "player": clean_player(r.player)} for r in results
            ],
            "method": "weighted_euclidean_normalised",
            "explanation": (
                f"Players were ranked by similarity to {reference_player.get('player_name')} using "
                f"min-max normalised per-90 output, progression and defensive metrics, combined into a "
                f"weighted Euclidean distance and converted to a 0-100 similarity score."
            ),
        }
        body, status, headers = json_response(response, origin=_origin(req))
        _log_call("/api/similarity", status)
        return func.HttpResponse(body, status_code=status, headers=headers)
    except Exception as exc:
        log_safe_exception("similarity", exc)
        body, status, headers = error_response("Unable to compute similarity right now.", status_code=500, origin=_origin(req), code="internal_error")
        _log_call("/api/similarity", status, "internal_error")
        return func.HttpResponse(body, status_code=status, headers=headers)


# -----------------------------------------------------------------------------
# POST /api/tactical-fit
# -----------------------------------------------------------------------------

@app.route(route="tactical-fit", methods=["POST", "OPTIONS"])
def tactical_fit_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _options_response(req)

    if (limited := _rate_limit_check(req)) is not None:
        return limited

    try:
        payload = req.get_json()
        request_model = TacticalFitRequest(**payload)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        log_safe_exception("tactical_fit.validation", exc)
        body, status, headers = error_response("Invalid request body.", status_code=400, origin=_origin(req), code="validation_error")
        _log_call("/api/tactical-fit", status, "validation_error")
        return func.HttpResponse(body, status_code=status, headers=headers)

    try:
        store = get_data_store()
        player = store.get_player(request_model.player_id)
        team = store.get_team_profile(request_model.team_name)

        if not player:
            body, status, headers = error_response("player_id not found.", status_code=404, origin=_origin(req), code="not_found")
            _log_call("/api/tactical-fit", status, "not_found")
            return func.HttpResponse(body, status_code=status, headers=headers)
        if not team:
            available = ", ".join(t["team_name"] for t in store.get_team_profiles())
            body, status, headers = error_response(f"team_name not found. Available teams: {available}", status_code=404, origin=_origin(req), code="not_found")
            _log_call("/api/tactical-fit", status, "not_found")
            return func.HttpResponse(body, status_code=status, headers=headers)

        all_players = store.get_players()
        fit = compute_tactical_fit(player, team, all_players)

        response = {
            "player": clean_player(player),
            "team": team,
            "fit_score": fit["fit_score"],
            "strengths": fit["strengths"],
            "risks": fit["risks"],
            "explanation": fit["explanation"],
        }
        body, status, headers = json_response(response, origin=_origin(req))
        _log_call("/api/tactical-fit", status)
        return func.HttpResponse(body, status_code=status, headers=headers)
    except Exception as exc:
        log_safe_exception("tactical_fit", exc)
        body, status, headers = error_response("Unable to compute tactical fit right now.", status_code=500, origin=_origin(req), code="internal_error")
        _log_call("/api/tactical-fit", status, "internal_error")
        return func.HttpResponse(body, status_code=status, headers=headers)


# -----------------------------------------------------------------------------
# POST /api/scout
# -----------------------------------------------------------------------------

@app.route(route="scout", methods=["POST", "OPTIONS"])
def scout_endpoint(req: func.HttpRequest) -> func.HttpResponse:
    if req.method == "OPTIONS":
        return _options_response(req)

    if (limited := _rate_limit_check(req)) is not None:
        return limited

    try:
        payload = req.get_json()
        request_model = ScoutQueryRequest(**payload)
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        log_safe_exception("scout.validation", exc)
        body, status, headers = error_response(
            f"Invalid request body. 'query' is required and must be 1-500 characters.",
            status_code=400, origin=_origin(req), code="validation_error",
        )
        _log_call("/api/scout", status, "validation_error")
        return func.HttpResponse(body, status_code=status, headers=headers)

    try:
        response = run_scout_workflow(request_model.query)
        body, status, headers = json_response(response, origin=_origin(req))
        _log_call("/api/scout", status)
        return func.HttpResponse(body, status_code=status, headers=headers)
    except Exception as exc:
        log_safe_exception("scout", exc)
        body, status, headers = error_response("Unable to process this scouting query right now.", status_code=500, origin=_origin(req), code="internal_error")
        _log_call("/api/scout", status, "internal_error")
        return func.HttpResponse(body, status_code=status, headers=headers)


# -----------------------------------------------------------------------------
# Optional FBref data pipeline (daily timer trigger)
#
# Disabled unless FBREF_PIPELINE_ENABLED=true and AZURE_SQL_CONNECTION_STRING
# is configured (see docs/FBREF_PIPELINE.md). Runs once a day at 03:00 UTC -
# well after FBref has finished updating stats for matches played the
# previous day, and far below any rate limit.
# -----------------------------------------------------------------------------

@app.timer_trigger(schedule="0 0 3 * * *", arg_name="timer", run_on_startup=False, use_monitor=True)
def fbref_daily_pipeline(timer: func.TimerRequest) -> None:
    settings = get_settings()
    if not settings.fbref_pipeline_enabled:
        logger.info("fbref_daily_pipeline: skipped (FBREF_PIPELINE_ENABLED is not true)")
        return

    try:
        from pipeline.run_pipeline import run as run_fbref_pipeline

        summary = run_fbref_pipeline()
        logger.info("fbref_daily_pipeline: %s", summary)
    except Exception as exc:
        log_safe_exception("fbref_daily_pipeline", exc)
