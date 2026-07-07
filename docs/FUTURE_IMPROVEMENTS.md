# Future Improvements

Ideas for extending FootballQ AI beyond its current scope as a free-tier
portfolio demo. None of these are required for the project to function.

## Data

- Replace the static 33-player sample dataset with a periodically refreshed
  feed from a free/open football statistics source, with a scheduled
  (low-frequency) Azure Function to refresh Azure SQL.
- Expand the dataset to more leagues, positions, and a larger candidate pool
  for similarity and tactical-fit comparisons.
- Add historical season-over-season data to support trend analysis (e.g.
  "is this player improving?").

## Agent workflow

- Migrate `shared/agent_workflow.py` to a real LangGraph `StateGraph` once
  cold-start cost is acceptable (e.g. if moving off Consumption plan, or once
  Azure Functions Flex Consumption reduces cold starts) — see the upgrade
  path in [AGENT_WORKFLOW.md](AGENT_WORKFLOW.md).
- Add a dedicated "follow-up question" agent so `/scout` supports multi-turn
  conversations with memory of previously discussed players.
- Expand the Query Classifier with more query types (e.g. "find a replacement
  for player X", set-piece specialists, injury-risk profiling).

## RAG

- Implement the Qdrant semantic-search path fully: embed `ScoutingNotes` and
  `TeamProfiles` with a free/low-cost embedding model and populate a Qdrant
  free-tier collection, with the existing SQL keyword fallback retained.
- Add a hybrid ranking that combines keyword and semantic scores.

## Scoring models

- Calibrate similarity metric weights using real outcome data (e.g. transfer
  success) rather than equal weighting.
- Add position-specific metric sets for similarity (e.g. goalkeepers would
  need save percentage, not progressive carries).
- Extend tactical fit to consider squad depth/needs, not just an individual
  player's profile.

## LLM

- When `ENABLE_REAL_LLM=true`, add response caching (e.g. by query hash) to
  reduce repeated API calls and cost.
- Add a configurable LLM provider abstraction so providers beyond OpenAI can
  be used.

## Frontend

- Add a saved-comparisons / shortlist feature (would require persistent user
  storage — currently out of scope to keep the app stateless and free).
- Add data visualisations on `/architecture` showing live request flow.
- Internationalisation for non-English scouting queries.

## Platform / operations

- Add Application Insights dashboards and alerting thresholds beyond the
  basic budget alerts in [COST_SAFETY.md](COST_SAFETY.md).
- Move rate limiting to a shared store (e.g. Azure Table Storage or Redis
  free tier) so it's consistent across scaled-out Function instances.
- Add end-to-end tests (e.g. Playwright) running against a deployed preview
  environment in CI.
- Add a staging environment (separate Vercel preview + separate Function App
  slot) for testing schema/data changes before they reach production.

## Security

- Add automated dependency vulnerability scanning to
  `.github/workflows/security-checks.yml` if not already comprehensive.
- Consider a managed WAF/API gateway in front of Azure Functions for stronger
  rate limiting and bot protection if traffic grows beyond demo levels.
