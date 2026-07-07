# MCP (Model Context Protocol) — Optional

FootballQ AI includes **optional, safe stubs** for exposing its read-only
business logic as MCP tools. **This is not required for the public website
to function**, and `MCP_ENABLED=false` by default — no deployed Azure
Function calls anything in this module.

## What's provided

`api/shared/mcp_tools.py` wraps the same functions used by `function_app.py`
and `agent_workflow.py` — a single source of truth, no duplicated logic:

| Function | Mirrors |
|---|---|
| `search_players(...)` | `GET /api/players` |
| `get_player_profile(player_id)` | `GET /api/players/{player_id}` |
| `compare_players(player_ids)` | `POST /api/compare` |
| `find_similar_players(reference_player_id, ...)` | `POST /api/similarity` |
| `tactical_fit_analysis(player_id, team_name)` | `POST /api/tactical-fit` |
| `generate_scouting_report_tool(player_id)` | scouting-report path of `/api/scout` |
| `scout_query(query)` | `POST /api/scout` |

## Security posture

- Every function is **read-oriented**: database reads plus
  similarity/comparison/tactical-fit/scouting computations. None of them
  execute shell commands, read/write arbitrary files, or expose environment
  variables, connection strings, or API keys.
- An MCP host wiring these up should still validate inputs with the same
  Pydantic models in `shared/schemas.py` before calling these functions —
  they do not re-validate on their own (the API endpoints do that via
  Pydantic; these are lower-level wrappers).
- `MCP_ENABLED` exists in `shared/config.py` precisely so that, if an MCP
  server is added later, it can check this flag before registering tools —
  keeping the optional surface explicitly opt-in.

## Why it's optional

The brief for this project is a public scouting **website**. An MCP server
is a separate integration surface (e.g. for use from Claude Desktop or
another MCP-aware client) that doesn't need to be deployed for the site to
work, and adding one to the public Azure Functions app would expand the
attack surface unnecessarily. Keeping it as importable, tested-by-association
functions means:

- A future MCP server (e.g. a small local script or separate deployment) can
  `from shared.mcp_tools import scout_query, find_similar_players, ...` and
  register them as tools with minimal glue code.
- The public API and any future MCP server always return consistent results,
  since both call the same underlying functions.

## If you want to wire up an MCP server

1. Create a small script (not part of the deployed Azure Function) that
   imports `api/shared/mcp_tools.py` and registers each function as an MCP
   tool using your MCP SDK of choice.
2. Set `MCP_ENABLED=true` only in that script's environment — the deployed
   public API's `MCP_ENABLED` should remain `false` unless you intend to
   expose MCP over HTTP, which would require its own auth and rate limiting.
3. Validate inputs with `shared/schemas.py` models before calling the
   wrapped functions, exactly as `function_app.py` does.
