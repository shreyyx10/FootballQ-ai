# API Reference

Base URL (production): `https://<your-function-app>.azurewebsites.net/api`
Base URL (local): `http://localhost:7071/api`

All endpoints:
- Validate input with Pydantic (`api/shared/schemas.py`).
- Support `OPTIONS` for CORS preflight (returns `204` with CORS headers if
  the request `Origin` is in `ALLOWED_ORIGINS`).
- Apply best-effort rate limiting (`429` with `code: "rate_limited"` if
  exceeded).
- Return errors as `{"error": {"code": "...", "message": "..."}}` — never a
  stack trace.

## `GET /api/health`

Health check.

```bash
curl https://<api-base>/api/health
```

```json
{ "status": "ok", "service": "FootballQ AI API", "mode": "free-demo" }
```

## `GET /api/players`

List players, with optional filters as query parameters.

| Param | Type | Constraints |
|---|---|---|
| `position` | string | max 100 chars |
| `league` | string | max 150 chars |
| `club` | string | max 150 chars |
| `age_min` / `age_max` | int | 14-50 |
| `minutes_min` | int | 0-6000 |

```bash
curl "https://<api-base>/api/players?position=Winger&age_max=23"
```

```json
{ "players": [ { "player_id": "p001", "player_name": "Lamine Yamal", "age": 18, "...": "..." } ], "count": 1 }
```

Invalid query parameters (e.g. `age_min=5`) return `400 validation_error`.

## `GET /api/players/{player_id}`

Fetch a single player's full statistical profile.

```bash
curl https://<api-base>/api/players/p001
```

```json
{ "player": { "player_id": "p001", "player_name": "Lamine Yamal", "...": "..." } }
```

- `400 validation_error` if `player_id` doesn't match `^[a-zA-Z0-9_\-]{1,50}$`.
- `404 not_found` if no player with that ID exists.

## `POST /api/compare`

Compare 2-5 players side by side.

**Request body:**

```json
{ "player_ids": ["p001", "p002"] }
```

- `player_ids`: 2-5 unique strings, each matching the player-ID pattern.

```bash
curl -X POST https://<api-base>/api/compare \
  -H "Content-Type: application/json" \
  -d '{"player_ids": ["p001", "p002"]}'
```

**Response:**

```json
{
  "players": [ /* cleaned player objects */ ],
  "comparison_table": [ { "metric": "xg", "label": "Expected Goals (xG)", "values": { "p001": 7.8, "p002": 5.2 } } ],
  "...": "additional fields from shared/comparison.py (strengths/weaknesses per player)"
}
```

- `400 validation_error` if `player_ids` is missing, has <2 or >5 entries,
  contains duplicates, or contains an invalid ID format.
- `404 not_found` with `Unknown player_id(s): ...` if any ID doesn't exist.

## `POST /api/similarity`

Find players statistically similar to a reference player.

**Request body:**

```json
{
  "reference_player_id": "p001",
  "filters": { "position": "Winger", "age_max": 23, "age_min": 16, "minutes_min": 500, "league": "La Liga" },
  "top_n": 5
}
```

- `reference_player_id`: required, valid player-ID format.
- `filters`: optional; all fields optional. If omitted, candidates default to
  the reference player's own `position`.
- `top_n`: 1-20, default 5.

```bash
curl -X POST https://<api-base>/api/similarity \
  -H "Content-Type: application/json" \
  -d '{"reference_player_id": "p001", "top_n": 5}'
```

**Response:**

```json
{
  "reference_player": { "...": "cleaned player object" },
  "similar_players": [
    {
      "player": { "...": "cleaned player object" },
      "similarity_score": 87.4,
      "closest_metrics": [ { "metric": "xag", "label": "Expected Assists (xAG)", "reference_value": 9.6, "candidate_value": 9.1 } ],
      "biggest_differences": [ { "metric": "...", "label": "...", "reference_value": 0, "candidate_value": 0 } ]
    }
  ],
  "method": "weighted_euclidean_normalised",
  "explanation": "Players were ranked by similarity to ... using min-max normalised per-90 ..."
}
```

- `400 validation_error` for malformed input.
- `404 not_found` if `reference_player_id` doesn't exist.
- If filters yield ≤1 candidate, the full player pool is used instead.

## `POST /api/tactical-fit`

Assess how well a player fits a team's tactical identity.

**Request body:**

```json
{ "player_id": "p001", "team_name": "Barcelona" }
```

- `player_id`: required, valid player-ID format.
- `team_name`: required, max 100 chars, matches `^[\w\s\-'.,?!]{0,500}$`.

```bash
curl -X POST https://<api-base>/api/tactical-fit \
  -H "Content-Type: application/json" \
  -d '{"player_id": "p001", "team_name": "Barcelona"}'
```

**Response:**

```json
{
  "player": { "...": "cleaned player object" },
  "team": { "team_name": "Barcelona", "tactical_style": "...", "formation": "4-3-3", "pressing_intensity": "High", "possession_style": "Possession-heavy, short combinations", "player_requirements": "..." },
  "fit_score": 82,
  "strengths": [ "..." ],
  "risks": [ "..." ],
  "explanation": "..."
}
```

- `400 validation_error` for malformed input.
- `404 not_found` if `player_id` doesn't exist, or if `team_name` isn't one
  of the available teams (the error message lists available team names).

## `POST /api/scout`

Natural-language scouting query, processed by the multi-agent workflow.

**Request body:**

```json
{ "query": "Find me a young winger under 23 with strong dribbling and creativity" }
```

- `query`: required, 1-500 characters (after trimming).

```bash
curl -X POST https://<api-base>/api/scout \
  -H "Content-Type: application/json" \
  -d '{"query": "Compare Lamine Yamal and Jude Bellingham"}'
```

**Response:**

```json
{
  "answer": "string - full narrative answer covering the direct answer, why these players, tactical notes, and a final recommendation",
  "recommended_players": [ /* cleaned player objects, 0-5 */ ],
  "supporting_statistics": [ { "player_id": "p001", "player_name": "Lamine Yamal", "goals": 9, "assists": 12, "xg": 7.8, "xag": 9.6, "progressive_carries_per90": 5.8, "shot_creating_actions_per90": 4.9, "pass_completion_pct": 84.2, "minutes": 2450 } ],
  "retrieved_context_summary": [ "Scouting note retrieved for Lamine Yamal.", "..." ],
  "workflow_summary": [ "Safety agent screened the input for unsafe or out-of-scope requests.", "Query classifier identified this as a 'player comparison' request.", "..." ],
  "confidence_level": "High",
  "limitations": [ "All data is sample/demo data for a free-tier portfolio project and should not be used for real transfer or scouting decisions." ]
}
```

- `400 validation_error` if `query` is missing, empty, or >500 characters.
- Queries containing prompt-injection-style patterns are still processed for
  their football content; `limitations` notes that suspicious patterns were
  ignored.
- `workflow_summary` never contains hidden chain-of-thought — only short,
  human-readable summaries of each agent's contribution.

## Example queries for `/api/scout`

- `"Find me a young winger under 23 with strong dribbling and creativity"`
  → `player_search`
- `"Compare Lamine Yamal and Jude Bellingham"` → `player_comparison`
- `"Find players similar to Lamine Yamal"` → `player_similarity`
- `"Would a high-pressing midfielder suit Barcelona's system?"` →
  `tactical_fit`
- `"Generate a scouting report for Lamine Yamal"` → `scouting_report`
- `"What is FootballQ AI?"` → `general_question`

## Error codes

| HTTP status | `code` | Meaning |
|---|---|---|
| 400 | `validation_error` | Request failed Pydantic validation. |
| 404 | `not_found` | Referenced player/team doesn't exist. |
| 429 | `rate_limited` | Too many requests from this client in the current window. |
| 500 | `internal_error` | Unexpected server error — details logged server-side only. |
