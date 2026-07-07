# Apify Integration Evaluation (Decision Note)

**Date:** 2026-07-03
**Status:** Decided — keep the `requests`-based scraper (`api/pipeline/fbref_scraper.py`). No Apify integration.
**Context:** Apify MCP was connected to explore replacing `fetch_html()` or running the historical backfill via Apify actors to avoid FBref rate limits.

## Options evaluated

### 1. Dedicated FBref actors on the Apify Store — rejected

Two actors exist as of July 2026. Neither comes close to covering this pipeline's schema.

| | [parseforge/fbref-scraper](https://apify.com/parseforge/fbref-scraper) | [crawlerbros/fbref-scraper](https://apify.com/crawlerbros/fbref-scraper) |
|---|---|---|
| Pricing | $19 / 1,000 results | $3 / 1,000 results |
| Total users | 6 (created May 2026) | 3 (created June 2026) |
| Ratings | 0 | 0 |
| Fields returned | ~22 (standard stats only) | ~16 (standard stats only) |
| Leagues | Big 5 + UCL + UEL | Big 5 only |
| Data freshness | "Most recent **archived** version" — can lag live FBref by days | Live scrape |

Coverage gaps against this pipeline's requirements:

- **9 of 10 stat categories missing.** Both actors return only standard stats. No shooting, passing, possession, defense, gca, keepers, keepersadv, playingtime, or misc — i.e. most of `dbo.Players` and nearly all GK/playing-time/misc columns of `dbo.PlayerSeasonStats`.
- **5 of 10 leagues missing.** No Championship, Eredivisie, Primeira Liga, Brazilian Serie A, or Liga Profesional Argentina.
- **No squad stats** (`dbo.TeamStats`) and **no match logs** (`dbo.MatchLogs`). (parseforge's README mentions match logs; its input schema and output fields expose only player standard stats.)
- **Vendor risk.** Both are near-zero-usage community actors with no ratings, weeks old. A daily production pipeline shouldn't depend on either.

Cost at their coverage level is also unfavorable: ~3,000 players/day across leagues would be ~$9–57/day for a fraction of the current data.

### 2. Generic actors / Apify Proxy as a `fetch_html()` transport — rejected

Keeping our parsing (`extract_table`, `transform.py`) and swapping only the HTTP layer for an Apify Cheerio/Web Scraper run or Apify Proxy is technically straightforward. Rejected because:

- **It only "works" by evading FBref's blocks.** FBref's `Crawl-delay` and rate limiting are deliberate policy from Sports Reference. Rotating residential IPs to bypass them conflicts with their terms of use and risks the data source entirely. The current scraper (6s delay, honest User-Agent, robots.txt compliance) is the sustainable, compliant approach.
- **Our volumes don't justify it.** Daily run ≈ 20 fetches ≈ 2 minutes. Full 10-league × 5-season backfill ≈ 500 fetches ≈ 50 minutes, one-time, interrupt-safe, and idempotent on re-run.
- Adds a paid dependency, a new failure mode, and per-run latency to solve a problem we don't have.

### 3. Keep `requests` scraper — **chosen**

No changes required. The existing design (RateLimiter from robots.txt Crawl-delay, page cache, 429 backoff, graceful skips) already handles FBref correctly.

## Revisit trigger

Reconsider only if the deployed Azure Function starts receiving persistent 403s because FBref/Cloudflare blocks Azure datacenter egress IPs. Options at that point, in order of preference:

1. Run the scrape from a non-datacenter environment (e.g. local/scheduled machine) and push to Azure SQL.
2. An Apify-based fallback inside `fetch_html()` — with the caveat that the terms-of-use concern above applies.

## Trial-run verification

Hands-on 10-record trial runs of both actors via the Apify MCP were attempted on 2026-07-03 but blocked by an invalid Apify API token. Field coverage above is taken from both actors' published READMEs, input schemas, and sample outputs. A trial run would only confirm the documented gap; it would not change the decision.
