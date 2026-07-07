"""Tests for Pydantic request validation and validation-related API responses."""

import json

import azure.functions as func
import pytest
from pydantic import ValidationError

import function_app
from shared.schemas import (
    ComparePlayersRequest,
    PlayerQueryParams,
    ScoutQueryRequest,
    SimilarityRequest,
    TacticalFitRequest,
)
from shared.security import MAX_QUERY_LENGTH


def _request(method, route, route_params=None, params=None, body=None):
    return func.HttpRequest(
        method=method,
        url=f"/api/{route}",
        params=params or {},
        route_params=route_params or {},
        headers={},
        body=json.dumps(body).encode("utf-8") if body is not None else b"",
    )


# --- Pydantic schema validation -------------------------------------------

def test_compare_players_request_requires_at_least_two_ids():
    with pytest.raises(ValidationError):
        ComparePlayersRequest(player_ids=["p001"])


def test_compare_players_request_rejects_invalid_id_format():
    with pytest.raises(ValidationError):
        ComparePlayersRequest(player_ids=["p001", "bad id!"])


def test_compare_players_request_rejects_duplicates():
    with pytest.raises(ValidationError):
        ComparePlayersRequest(player_ids=["p001", "p001"])


def test_compare_players_request_accepts_valid_ids():
    req = ComparePlayersRequest(player_ids=["p001", "p002"])
    assert req.player_ids == ["p001", "p002"]


def test_similarity_request_rejects_invalid_reference_id():
    with pytest.raises(ValidationError):
        SimilarityRequest(reference_player_id="../etc/passwd")


def test_similarity_request_top_n_bounds():
    with pytest.raises(ValidationError):
        SimilarityRequest(reference_player_id="p001", top_n=21)
    with pytest.raises(ValidationError):
        SimilarityRequest(reference_player_id="p001", top_n=0)


def test_tactical_fit_request_rejects_invalid_player_id():
    with pytest.raises(ValidationError):
        TacticalFitRequest(player_id="bad id", team_name="Arsenal")


def test_scout_query_request_rejects_empty_query():
    with pytest.raises(ValidationError):
        ScoutQueryRequest(query="")


def test_scout_query_request_rejects_too_long_query():
    with pytest.raises(ValidationError):
        ScoutQueryRequest(query="x" * (MAX_QUERY_LENGTH + 1))


def test_player_query_params_strips_whitespace():
    params = PlayerQueryParams(position="  Striker  ")
    assert params.position == "Striker"


# --- API-level validation responses ----------------------------------------

def test_get_player_invalid_id_returns_400():
    req = _request("GET", "players/{player_id}", route_params={"player_id": "../../etc"})
    resp = function_app.get_player(req)
    assert resp.status_code == 400
    body = json.loads(resp.get_body())
    assert body["error"]["code"] == "validation_error"


def test_get_player_unknown_valid_id_returns_404():
    req = _request("GET", "players/{player_id}", route_params={"player_id": "p999"})
    resp = function_app.get_player(req)
    assert resp.status_code == 404
    body = json.loads(resp.get_body())
    assert body["error"]["code"] == "not_found"


def test_compare_endpoint_rejects_single_player_id():
    req = _request("POST", "compare", body={"player_ids": ["p001"]})
    resp = function_app.compare_players_endpoint(req)
    assert resp.status_code == 400
    body = json.loads(resp.get_body())
    assert body["error"]["code"] == "validation_error"


def test_scout_endpoint_rejects_overly_long_query():
    req = _request("POST", "scout", body={"query": "x" * (MAX_QUERY_LENGTH + 1)})
    resp = function_app.scout_endpoint(req)
    assert resp.status_code == 400
    body = json.loads(resp.get_body())
    assert body["error"]["code"] == "validation_error"


def test_scout_endpoint_rejects_missing_query_field():
    req = _request("POST", "scout", body={})
    resp = function_app.scout_endpoint(req)
    assert resp.status_code == 400
