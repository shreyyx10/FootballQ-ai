"""Tests for GET /api/health."""

import json

import azure.functions as func

import function_app


def _make_request(method="GET", route_params=None, params=None, body=None, headers=None):
    return func.HttpRequest(
        method=method,
        url=f"/api/health",
        params=params or {},
        route_params=route_params or {},
        headers=headers or {},
        body=json.dumps(body).encode("utf-8") if body is not None else b"",
    )


def test_health_returns_ok():
    req = _make_request()
    resp = function_app.health(req)
    assert resp.status_code == 200

    body = json.loads(resp.get_body())
    assert body["status"] == "ok"
    assert body["service"] == "FootballQ AI API"
    assert body["mode"] == "free-demo"


def test_health_options_returns_no_content():
    req = _make_request(method="OPTIONS")
    resp = function_app.health(req)
    assert resp.status_code == 204
