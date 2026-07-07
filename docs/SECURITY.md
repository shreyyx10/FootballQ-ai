# Security Notes

FootballQ AI is built with **security-conscious controls for a public,
free-tier demo**. It is **not claimed to be unhackable**, and it should not
be used to store, process, or transmit real personal data, credentials, or
anything sensitive.

## Implemented controls

**Input validation.** Every API endpoint validates its input with Pydantic
models (`api/shared/schemas.py`) before any business logic runs. Player IDs
must match `^[a-zA-Z0-9_\-]{1,50}$`, team names are length- and
character-restricted, scout queries are limited to 1-500 characters, and
`/api/compare` accepts 2-5 unique player IDs only. Invalid input returns a
generic `400 validation_error` — never a stack trace.

**Parameterised SQL only.** `AzureSqlDataStore` (`api/shared/database.py`)
never builds SQL with string concatenation or f-strings containing user
input. All queries use `pyodbc` parameter placeholders (`?`).

**CORS allowlist.** `shared/security.get_cors_headers()` only returns
`Access-Control-Allow-Origin` for origins present in the `ALLOWED_ORIGINS`
environment variable. Requests from other origins receive a response with no
CORS header, so browsers block them.

**Rate limiting.** `shared/security.is_rate_limited()` applies a best-effort,
in-memory sliding-window limit (`RATE_LIMIT_MAX_REQUESTS` per
`RATE_LIMIT_WINDOW_SECONDS`, default 30/60s) keyed by `X-Forwarded-For`.
Because Azure Functions Consumption-plan instances are ephemeral and can
scale out, this is a guard against accidental abuse, not a substitute for an
API gateway or WAF.

**Safe error responses.** `shared/security.error_response()` and
`log_safe_exception()` ensure clients only ever see
`{"error": {"code": ..., "message": ...}}` with a short, generic message.
Exception types and truncated messages are logged server-side only, and
secrets (`AZURE_SQL_CONNECTION_STRING`, `OPENAI_API_KEY`, `QDRANT_API_KEY`)
are never logged or returned.

**Prompt-injection / unsafe-input heuristics.** `detect_prompt_injection()`
screens `/api/scout` queries for patterns such as "ignore previous
instructions", "reveal your system prompt", `DROP TABLE` / `UNION SELECT`,
`<script`, and attempts to extract secrets/connection strings. Matches do not
block the request — they add a note to the response's `limitations` field so
the user understands part of their input was disregarded. This is a
heuristic safety net, not a guarantee.

**No hidden chain-of-thought.** `/api/scout` responses include a concise,
human-readable `workflow_summary` describing what each agent did. The
underlying reasoning/prompting is never exposed in any response.

**Security headers.** Both the frontend (`vercel.json`, `next.config.js`)
and every API response (`shared/security.get_cors_headers()`) set
`X-Content-Type-Options: nosniff`. The frontend additionally sets
`X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`,
and a restrictive `Permissions-Policy`.

**Least-privilege database access.** `api/seed/schema.sql` documents creating
a dedicated SQL login with only `db_datareader` and `db_datawriter` — never
`db_owner` or `db_ddladmin` — for the application's connection string.

**Secret management.** `.env.example` contains placeholders only. Real
values are configured via Azure Functions Application Settings and Vercel
Environment Variables, never committed to source control (`.gitignore`
excludes `.env*`, `local.settings.json`).

## Known limitations

- Rate limiting is in-memory and per-instance — it resets on cold start and
  does not coordinate across scaled-out instances.
- The prompt-injection heuristics are pattern-based and can be bypassed by a
  determined attacker; they are a defence-in-depth measure, not a guarantee.
- The dataset is a small sample of real, well-known players' historical
  statistics for illustrative purposes — it is not live or comprehensive.
- This project has no dedicated security team or bug bounty. See the root
  [SECURITY.md](../SECURITY.md) for how to report an issue.

## Reporting a vulnerability

Open a GitHub issue describing the problem. Do not include real credentials,
tokens, or personal data in any report.
