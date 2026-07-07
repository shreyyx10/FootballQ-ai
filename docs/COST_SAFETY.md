# Cost Safety

FootballQ AI is designed to run at **$0/month** on free tiers. This page
explains why, and how to keep it that way.

## What's free, and why it stays free

| Component | Free tier | Why this project stays inside it |
|---|---|---|
| Vercel (frontend) | Hobby plan | A Next.js static/SSR site with 7 lightweight pages and no heavy server-side rendering loops. Hobby includes generous bandwidth and serverless function execution for personal/non-commercial projects. |
| Azure Functions (API) | Consumption plan free grant | Each request is a short-lived HTTP function (typically <1s). `host.json` sets `functionTimeout: 00:02:00` as a hard ceiling. Consumption plan includes a monthly free grant of executions and GB-seconds that this low-traffic demo will not approach. |
| Azure SQL Database | Free offer (one per subscription) | The schema is small (5 tables, sample data only) and queries are simple, indexed lookups — far below the free offer's storage and vCore limits. |
| OpenAI API | Not used by default | `USE_MOCK_LLM=true` and `ENABLE_REAL_LLM=false` by default — zero API calls, zero cost. |
| Qdrant | Not used by default | `ENABLE_QDRANT=false` by default — no vector DB provisioned. |

## Controls that prevent unexpected charges

1. **Mock LLM by default.** `shared/config.py` defaults `USE_MOCK_LLM=true`
   and `ENABLE_REAL_LLM=false`. Enabling a real LLM is an explicit opt-in
   that requires setting both `ENABLE_REAL_LLM=true` and `OPENAI_API_KEY`.
2. **Qdrant disabled by default.** `ENABLE_QDRANT=false`; the RAG retriever
   never calls an external vector service unless explicitly configured, and
   falls back safely if the call fails.
3. **Function timeout cap.** `api/host.json` sets a 2-minute
   `functionTimeout`, preventing a runaway request from consuming excessive
   GB-seconds.
4. **Rate limiting.** `RATE_LIMIT_ENABLED=true` by default limits each client
   to 30 requests/60 seconds, reducing the chance that a script or bot drives
   up execution counts.
5. **No background jobs / timers.** Every Azure Function is HTTP-triggered
   and only runs in response to a request — there are no scheduled functions
   that run (and bill) continuously.
6. **Small, static dataset.** The sample dataset (~30 players, scouting
   notes, team profiles) is tiny; Azure SQL storage stays a small fraction of
   the free offer's limit even with logging tables.
7. **Local-seed fallback.** If `AZURE_SQL_CONNECTION_STRING` is unset or a
   database call fails, the API serves from an in-memory dataset — so a
   misconfigured or paused database does not produce retries or errors that
   could otherwise be mistaken for load.

## Recommended monitoring

Even on free tiers, set up basic guardrails after deploying:

- In the Azure Portal, set a **budget alert** (e.g. $1) on the subscription
  used for Azure Functions and Azure SQL — free tiers can be exceeded if
  traffic unexpectedly spikes or a second resource is accidentally
  provisioned.
- In Vercel, monitor the **Usage** tab for bandwidth and function execution
  trends on the Hobby plan.
- If you ever set `ENABLE_REAL_LLM=true`, set a **hard spending limit** on
  your OpenAI account — this project does not implement its own LLM spend
  cap beyond rate limiting.

## If you outgrow the free tier

This is a portfolio project, not a production service. If traffic grows:

- Add a CDN/cache layer in front of `/api/players` (it changes rarely).
- Move rate limiting to an API Management layer or Azure Front Door, which
  coordinates across scaled-out Function instances.
- Consider Azure SQL's next pricing tier, or batch/cache common queries.

None of these are required for the demo as shipped.
