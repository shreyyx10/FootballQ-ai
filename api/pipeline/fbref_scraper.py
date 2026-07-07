"""
Rate-limited FBref scraper.

FBref (https://fbref.com, part of Sports Reference) publishes its
`robots.txt` with a `Crawl-delay` directive and actively rate-limits/blocks
clients that request pages too quickly. This module:

- Reads `robots.txt` once per process and respects its `Crawl-delay` for the
  default User-agent, falling back to `FBREF_REQUEST_DELAY_SECONDS`
  (default 6 seconds) if no directive is present or it can't be fetched.
- Enforces that delay between *every* HTTP request via `RateLimiter`,
  regardless of how many pages a single pipeline run touches.
- Sends a descriptive User-Agent identifying this as a low-volume,
  non-commercial scraper.
- Retries once on HTTP 429 with a longer backoff, then gives up for that
  page (the pipeline continues with whatever it already has).

This module does NOT attempt real-time/"every second" updates. FBref stats
are derived from completed matches and change at most a few times per day
during a busy match week - a daily run is more than sufficient. See
docs/FBREF_PIPELINE.md.
"""

from __future__ import annotations

import logging
import re
import time
import urllib.robotparser
from io import StringIO
from typing import Optional

import pandas as pd
import requests

from shared.config import get_settings

logger = logging.getLogger("footballq.pipeline.fbref_scraper")

FBREF_BASE = "https://fbref.com"
DEFAULT_USER_AGENT = (
    "FootballQAI-Pipeline/1.0 (+https://github.com/; portfolio project, "
    "low-volume daily scrape, contact via repository issues)"
)

# Big 5 European Leagues combined stat pages (one row per player across all
# five leagues). Each maps to the FBref table `id` containing the relevant
# per-90 metrics used by FootballQ AI's Players table, plus (for keepers,
# keepersadv, playingtime, misc) the extra categories stored in
# dbo.PlayerSeasonStats (see docs/FBREF_PIPELINE.md).
BIG5_PLAYER_STAT_PAGES: dict[str, tuple[str, str]] = {
    "standard": ("/en/comps/Big5/stats/players/Big-5-European-Leagues-Stats", "stats_standard"),
    "shooting": ("/en/comps/Big5/shooting/players/Big-5-European-Leagues-Stats", "stats_shooting"),
    "passing": ("/en/comps/Big5/passing/players/Big-5-European-Leagues-Stats", "stats_passing"),
    "possession": ("/en/comps/Big5/possession/players/Big-5-European-Leagues-Stats", "stats_possession"),
    "defense": ("/en/comps/Big5/defense/players/Big-5-European-Leagues-Stats", "stats_defense"),
    "gca": ("/en/comps/Big5/gca/players/Big-5-European-Leagues-Stats", "stats_gca"),
    "keepers": ("/en/comps/Big5/keepers/players/Big-5-European-Leagues-Stats", "stats_keeper"),
    "keepersadv": ("/en/comps/Big5/keepersadv/players/Big-5-European-Leagues-Stats", "stats_keeper_adv"),
    "playingtime": ("/en/comps/Big5/playingtime/players/Big-5-European-Leagues-Stats", "stats_playing_time"),
    "misc": ("/en/comps/Big5/misc/players/Big-5-European-Leagues-Stats", "stats_misc"),
}

BIG5_SQUAD_STATS_PAGE = ("/en/comps/Big5/stats/squads/Big-5-European-Leagues-Stats", "stats_squads_standard_for")

# URL path-segment/table-id pairs for a single (non-Big5) league's stat
# pages. `{id}` is the FBref competition id and `{slug}` is the URL-friendly
# competition name, both from pipeline/leagues.json (or pipeline/all_leagues.json
# for the historical backfill). Unlike the Big5 combined pages (which separate
# /stats/players/ and /stats/squads/), FBref's individual league pages use a
# flat `/en/comps/{id}/{type}/{slug}-Stats` pattern for the current season, or
# `/en/comps/{id}/{season}/{type}/{season}-{slug}-Stats` for a past season
# (verified live against comps 9, 10, 21, 23, 24, 32), and each page contains
# BOTH the squad table and the player table for that stat type.
LEAGUE_PLAYER_STAT_PAGE_TEMPLATES: dict[str, tuple[str, str]] = {
    "standard": ("stats", "stats_standard"),
    "shooting": ("shooting", "stats_shooting"),
    "passing": ("passing", "stats_passing"),
    "possession": ("possession", "stats_possession"),
    "defense": ("defense", "stats_defense"),
    "gca": ("gca", "stats_gca"),
    "keepers": ("keepers", "stats_keeper"),
    "keepersadv": ("keepersadv", "stats_keeper_adv"),
    "playingtime": ("playingtime", "stats_playing_time"),
    "misc": ("misc", "stats_misc"),
}

# Squad standard stats (`stats_squads_standard_for`) live on the same page as
# the "standard" player table above - no separate /stats/squads/ path exists
# for individual leagues.
LEAGUE_SQUAD_STATS_PAGE_TEMPLATE = ("stats", "stats_squads_standard_for")


def league_stat_path(fbref_comp_id: str, fbref_slug: str, stat_type: str, season: Optional[str] = None) -> str:
    """Build a single (non-Big5) league's stat-page path.

    `stat_type` is a URL path segment from `LEAGUE_PLAYER_STAT_PAGE_TEMPLATES`
    / `LEAGUE_SQUAD_STATS_PAGE_TEMPLATE` (e.g. "stats", "shooting", "keepers").
    If `season` is given (e.g. "2023-2024"), builds the historical-season URL
    instead of the current-season one.
    """
    if season:
        return f"/en/comps/{fbref_comp_id}/{season}/{stat_type}/{season}-{fbref_slug}-Stats"
    return f"/en/comps/{fbref_comp_id}/{stat_type}/{fbref_slug}-Stats"


# Identifying columns shared across all Big5 player stat tables, used to
# merge the separate stat tables into one row per player.
PLAYER_JOIN_COLUMNS = ["Player", "Squad", "Born"]


# -----------------------------------------------------------------------------
# Rate limiting
# -----------------------------------------------------------------------------

class RateLimiter:
    """Enforces a minimum delay between successive requests (per process)."""

    def __init__(self, delay_seconds: float):
        self.delay_seconds = max(delay_seconds, 1.0)
        self._last_request: Optional[float] = None

    def wait(self) -> None:
        if self._last_request is not None:
            elapsed = time.monotonic() - self._last_request
            remaining = self.delay_seconds - elapsed
            if remaining > 0:
                time.sleep(remaining)
        self._last_request = time.monotonic()


def _robots_crawl_delay(session: requests.Session, user_agent: str) -> Optional[float]:
    """Best-effort read of FBref's robots.txt Crawl-delay directive."""
    try:
        resp = session.get(f"{FBREF_BASE}/robots.txt", timeout=10, headers={"User-Agent": user_agent})
        resp.raise_for_status()
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(resp.text.splitlines())
        delay = parser.crawl_delay(user_agent) or parser.crawl_delay("*")
        return float(delay) if delay is not None else None
    except Exception as exc:  # pragma: no cover - network dependent
        logger.warning("Could not read FBref robots.txt, using default delay: %s", type(exc).__name__)
        return None


def build_rate_limiter(session: Optional[requests.Session] = None) -> RateLimiter:
    settings = get_settings()
    configured_delay = settings.fbref_request_delay_seconds
    if settings.fbref_fetch_mode == "wayback":
        # Requests go to web.archive.org, not fbref.com - FBref's robots.txt
        # is irrelevant (and unreachable to scripts anyway). The configured
        # delay is still enforced out of politeness to the Internet Archive.
        logger.info("Wayback fetch mode: rate limit %.1fs between requests", configured_delay)
        return RateLimiter(configured_delay)
    session = session or requests.Session()
    robots_delay = _robots_crawl_delay(session, settings.fbref_user_agent)
    delay = max(configured_delay, robots_delay or 0.0)
    logger.info("FBref pipeline rate limit: %.1fs between requests", delay)
    return RateLimiter(delay)


# -----------------------------------------------------------------------------
# Fetching
# -----------------------------------------------------------------------------

# Per-process page cache. Individual (non-Big5) league pages now serve both
# the squad standard-stats table and the player standard-stats table from the
# same URL (/en/comps/{id}/stats/{slug}-Stats), so a single pipeline run can
# request the same page twice (once via scrape_league_player_stats, once via
# scrape_league_squad_stats). Caching avoids a redundant fetch + rate-limit
# wait for that case.
_PAGE_CACHE: dict[str, Optional[str]] = {}


def fetch_html(path_or_url: str, session: requests.Session, rate_limiter: RateLimiter) -> Optional[str]:
    """Fetch an FBref page, respecting the rate limiter. Returns None on failure.

    Depending on FBREF_FETCH_MODE this fetches either directly from
    fbref.com ("direct") or from the page's most recent Wayback Machine
    snapshot ("wayback", default). FBref/Cloudflare returns HTTP 403 to all
    non-browser clients as of 2026, so "direct" only exists in case that
    policy is relaxed. Wayback snapshots contain the original page HTML
    (including FBref's commented-out tables), so `extract_table` works
    unchanged; the data lags the live site by however old the snapshot is.
    """
    url = path_or_url if path_or_url.startswith("http") else f"{FBREF_BASE}{path_or_url}"
    if url in _PAGE_CACHE:
        return _PAGE_CACHE[url]

    settings = get_settings()
    headers = {"User-Agent": settings.fbref_user_agent}

    if settings.fbref_fetch_mode == "wayback":
        html = _fetch_via_wayback(url, session, rate_limiter, headers)
    else:
        html = _fetch_direct(url, session, rate_limiter, headers)
    _PAGE_CACHE[url] = html
    return html


def _fetch_direct(
    url: str, session: requests.Session, rate_limiter: RateLimiter, headers: dict[str, str]
) -> Optional[str]:
    for _attempt in (1, 2):
        rate_limiter.wait()
        try:
            resp = session.get(url, headers=headers, timeout=30)
        except requests.RequestException as exc:
            logger.warning("FBref request failed for %s: %s", url, type(exc).__name__)
            return None

        if resp.status_code == 429:
            logger.warning("FBref rate-limited us (429) for %s, backing off", url)
            time.sleep(rate_limiter.delay_seconds * 3)
            continue
        if resp.status_code != 200:
            logger.warning("FBref returned HTTP %s for %s", resp.status_code, url)
            return None
        return resp.text
    return None


_WAYBACK_AVAILABILITY_API = "https://archive.org/wayback/available"
_WAYBACK_SAVE_URL = "https://web.archive.org/save/"
_WAYBACK_TIMESTAMP_RE = re.compile(r"/web/(\d{14})/")

# Save Page Now is a heavier operation for the Internet Archive than a
# snapshot read, so enforce extra spacing between save requests on top of
# the normal rate limiter.
_SPN_MIN_INTERVAL_SECONDS = 15.0
_last_spn_request: Optional[float] = None


def _fetch_via_wayback(
    url: str, session: requests.Session, rate_limiter: RateLimiter, headers: dict[str, str]
) -> Optional[str]:
    """Fetch `url`'s content via the Wayback Machine.

    1. Look up the most recent snapshot (availability API).
    2. If it's fresh enough (FBREF_WAYBACK_MAX_SNAPSHOT_AGE_DAYS), fetch it.
    3. Otherwise ask Save Page Now to capture the live page (the Archive's
       crawler can reach FBref even though scripts can't) and use that.
    4. If the save fails (quota, outage), fall back to the stale snapshot.

    Snapshot URLs get an `id_` flag inserted after the timestamp so the
    Archive serves the original raw HTML (including FBref's commented-out
    tables) instead of the rewritten page with the Wayback toolbar.
    """
    settings = get_settings()
    snapshot_ts, snapshot_url = _wayback_latest_snapshot(url, session, rate_limiter, headers)

    if snapshot_url and _snapshot_age_days(snapshot_ts) <= settings.fbref_wayback_max_snapshot_age_days:
        logger.info("Wayback snapshot %s (fresh) for %s", snapshot_ts, url)
        return _fetch_wayback_snapshot(snapshot_url, session, rate_limiter, headers)

    saved_html = _wayback_save_page_now(url, session, rate_limiter, headers)
    if saved_html is not None:
        return saved_html

    if snapshot_url:
        logger.warning(
            "Save Page Now failed for %s; falling back to stale snapshot %s", url, snapshot_ts
        )
        return _fetch_wayback_snapshot(snapshot_url, session, rate_limiter, headers)

    logger.warning("No Wayback snapshot exists for %s and Save Page Now failed", url)
    return None


def _wayback_latest_snapshot(
    url: str, session: requests.Session, rate_limiter: RateLimiter, headers: dict[str, str]
) -> tuple[Optional[str], Optional[str]]:
    """Return (timestamp, raw-content snapshot URL) of the latest snapshot, or (None, None)."""
    rate_limiter.wait()
    try:
        resp = session.get(
            _WAYBACK_AVAILABILITY_API,
            params={"url": url, "timestamp": time.strftime("%Y%m%d%H%M%S")},
            headers=headers,
            timeout=30,
        )
        resp.raise_for_status()
        closest = (resp.json().get("archived_snapshots") or {}).get("closest") or {}
    except (requests.RequestException, ValueError) as exc:
        logger.warning("Wayback availability lookup failed for %s: %s", url, type(exc).__name__)
        return None, None

    snapshot_url = closest.get("url")
    if not closest.get("available") or not snapshot_url:
        return None, None

    snapshot_url = _WAYBACK_TIMESTAMP_RE.sub(r"/web/\1id_/", snapshot_url)
    if snapshot_url.startswith("http://"):
        snapshot_url = "https://" + snapshot_url[len("http://"):]
    return closest.get("timestamp"), snapshot_url


def _snapshot_age_days(timestamp: Optional[str]) -> float:
    """Age of a Wayback timestamp (YYYYMMDDhhmmss) in days; inf if unparseable."""
    if not timestamp:
        return float("inf")
    try:
        then = time.mktime(time.strptime(timestamp[:14], "%Y%m%d%H%M%S"))
    except ValueError:
        return float("inf")
    # Wayback timestamps are UTC; time.mktime assumes local. The error is at
    # most a day's worth of timezone offset, which is fine for this check.
    return max(0.0, (time.time() - then) / 86400.0)


def _fetch_wayback_snapshot(
    snapshot_url: str, session: requests.Session, rate_limiter: RateLimiter, headers: dict[str, str]
) -> Optional[str]:
    for _attempt in (1, 2):
        rate_limiter.wait()
        try:
            resp = session.get(snapshot_url, headers=headers, timeout=60)
        except requests.RequestException as exc:
            logger.warning("Wayback fetch failed for %s: %s", snapshot_url, type(exc).__name__)
            return None
        if resp.status_code == 429:
            logger.warning("Wayback rate-limited us (429), backing off")
            time.sleep(rate_limiter.delay_seconds * 3)
            continue
        if resp.status_code != 200:
            logger.warning("Wayback returned HTTP %s for %s", resp.status_code, snapshot_url)
            return None
        return resp.text
    return None


def _wayback_save_page_now(
    url: str, session: requests.Session, rate_limiter: RateLimiter, headers: dict[str, str]
) -> Optional[str]:
    """Ask Save Page Now to capture `url`; return the captured page's raw HTML.

    Anonymous SPN blocks until the capture finishes and redirects to the new
    snapshot. It is quota-limited, so failures are expected occasionally -
    callers fall back to the latest existing snapshot.
    """
    global _last_spn_request
    if _last_spn_request is not None:
        wait = _SPN_MIN_INTERVAL_SECONDS - (time.monotonic() - _last_spn_request)
        if wait > 0:
            time.sleep(wait)

    rate_limiter.wait()
    _last_spn_request = time.monotonic()
    try:
        resp = session.get(_WAYBACK_SAVE_URL + url, headers=headers, timeout=180)
    except requests.RequestException as exc:
        logger.warning("Save Page Now request failed for %s: %s", url, type(exc).__name__)
        return None

    if resp.status_code == 429:
        logger.warning("Save Page Now rate-limited us (429) for %s; retrying once in 60s", url)
        time.sleep(60)
        _last_spn_request = time.monotonic()
        try:
            resp = session.get(_WAYBACK_SAVE_URL + url, headers=headers, timeout=180)
        except requests.RequestException as exc:
            logger.warning("Save Page Now retry failed for %s: %s", url, type(exc).__name__)
            return None

    if resp.status_code != 200 or "/web/" not in resp.url:
        logger.warning("Save Page Now returned HTTP %s for %s", resp.status_code, url)
        return None

    logger.info("Save Page Now captured %s -> %s", url, resp.url)
    # resp.text is the Wayback-rewritten page (toolbar + rewritten links);
    # the stat tables and FBref's commented-out tables are preserved, so
    # extract_table works on it directly. Re-fetching the id_ raw version
    # would cost an extra request for no parsing benefit.
    return resp.text


# -----------------------------------------------------------------------------
# Table extraction
# -----------------------------------------------------------------------------

_COMMENT_TABLE_RE = re.compile(r"<!--(.*?-->)", re.DOTALL)


def extract_table(html: str, table_id: str) -> Optional[pd.DataFrame]:
    """Extract a table by `id` from FBref HTML.

    FBref wraps many secondary tables inside HTML comments (to deter naive
    scraping). This first tries the visible DOM, then falls back to
    searching commented-out fragments for the same table id.
    """
    candidates = [html]
    for match in _COMMENT_TABLE_RE.finditer(html):
        if f'id="{table_id}"' in match.group(1):
            candidates.append(match.group(1))

    for fragment in candidates:
        try:
            tables = pd.read_html(StringIO(fragment), attrs={"id": table_id})
        except ValueError:
            continue
        if tables:
            return tables[0]
    return None


def flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse FBref's two-level column headers into single names.

    FBref tables have a top-level grouping header (e.g. "Per 90 Minutes")
    and a sub-header (e.g. "Gls"). We keep the sub-header as the column
    name, since it is what's referenced in transform.py's column map.
    Duplicate sub-headers (e.g. "Gls" appears in both "Performance" and
    "Per 90 Minutes") are disambiguated by prefixing with the group name.
    """
    if not isinstance(df.columns, pd.MultiIndex):
        return df

    seen: dict[str, int] = {}
    new_columns: list[str] = []
    for top, sub in df.columns:
        name = sub if sub and not str(sub).startswith("Unnamed") else top
        if name in seen:
            name = f"{top}_{sub}"
        seen[name] = seen.get(name, 0) + 1
        new_columns.append(name)
    df = df.copy()
    df.columns = new_columns
    return df


def _drop_summary_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Drop FBref's repeated header / summary rows that appear mid-table."""
    if "Player" not in df.columns:
        return df
    return df[df["Player"].notna() & (df["Player"] != "Player")].reset_index(drop=True)


# -----------------------------------------------------------------------------
# High-level scrape functions
# -----------------------------------------------------------------------------

def _scrape_player_stat_pages(
    pages: dict[str, tuple[str, str]],
    session: requests.Session,
    rate_limiter: RateLimiter,
) -> pd.DataFrame:
    """Fetch and merge a set of player-stat table pages into one DataFrame.

    Shared by `scrape_big5_player_stats` and `scrape_league_player_stats`.
    Returns one row per player, merged on `PLAYER_JOIN_COLUMNS`. Missing or
    unavailable tables are skipped gracefully.
    """
    merged: Optional[pd.DataFrame] = None
    for name, (path, table_id) in pages.items():
        html = fetch_html(path, session, rate_limiter)
        if html is None:
            logger.warning("Skipping %s table (fetch failed)", name)
            continue
        table = extract_table(html, table_id)
        if table is None:
            logger.warning("Skipping %s table (table id %s not found)", name, table_id)
            continue

        table = flatten_columns(table)
        table = _drop_summary_rows(table)

        if merged is None:
            merged = table
            continue

        join_cols = [c for c in PLAYER_JOIN_COLUMNS if c in table.columns and c in merged.columns]
        if not join_cols:
            logger.warning("Skipping %s table (no shared join columns)", name)
            continue

        new_cols = [c for c in table.columns if c not in merged.columns or c in join_cols]
        merged = merged.merge(table[new_cols], on=join_cols, how="left", suffixes=("", f"_{name}"))

    return merged if merged is not None else pd.DataFrame()


def _scrape_squad_stats_page(
    path: str,
    table_id: str,
    session: requests.Session,
    rate_limiter: RateLimiter,
) -> pd.DataFrame:
    """Fetch a single squad (team) standard-stats table page.

    Shared by `scrape_big5_squad_stats` and `scrape_league_squad_stats`.
    """
    html = fetch_html(path, session, rate_limiter)
    if html is None:
        return pd.DataFrame()
    table = extract_table(html, table_id)
    if table is None:
        return pd.DataFrame()
    table = flatten_columns(table)
    if "Squad" in table.columns:
        table = table[table["Squad"].notna() & (table["Squad"] != "Squad")].reset_index(drop=True)
    return table


def scrape_big5_player_stats(
    session: Optional[requests.Session] = None,
    rate_limiter: Optional[RateLimiter] = None,
) -> pd.DataFrame:
    """Scrape and merge the Big 5 leagues' player stat tables into one DataFrame.

    Returns one row per player with columns from `standard`, `shooting`,
    `passing`, `possession`, `defense`, and `gca` tables, flattened and
    merged on PLAYER_JOIN_COLUMNS. Missing/unavailable tables are skipped
    gracefully (the merged frame just has fewer columns).
    """
    session = session or requests.Session()
    rate_limiter = rate_limiter or build_rate_limiter(session)
    return _scrape_player_stat_pages(BIG5_PLAYER_STAT_PAGES, session, rate_limiter)


def scrape_big5_squad_stats(
    session: Optional[requests.Session] = None,
    rate_limiter: Optional[RateLimiter] = None,
) -> pd.DataFrame:
    """Scrape the Big 5 leagues' squad (team) standard stats table."""
    session = session or requests.Session()
    rate_limiter = rate_limiter or build_rate_limiter(session)

    path, table_id = BIG5_SQUAD_STATS_PAGE
    return _scrape_squad_stats_page(path, table_id, session, rate_limiter)


def scrape_league_player_stats(
    fbref_comp_id: str,
    fbref_slug: str,
    session: Optional[requests.Session] = None,
    rate_limiter: Optional[RateLimiter] = None,
    season: Optional[str] = None,
    categories: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Scrape and merge a single league's player stat tables into one DataFrame.

    `fbref_comp_id` and `fbref_slug` come from `pipeline/leagues.json` /
    `pipeline/all_leagues.json` (see docs/FBREF_PIPELINE.md for how to
    find/verify these on fbref.com).

    `season` (e.g. "2023-2024"): if given, scrapes that historical season's
    pages instead of the current season (used by the one-time backfill
    script, `pipeline/backfill_history.py`).

    `categories`: optional subset of `LEAGUE_PLAYER_STAT_PAGE_TEMPLATES` keys
    to scrape (defaults to all of them).
    """
    session = session or requests.Session()
    rate_limiter = rate_limiter or build_rate_limiter(session)
    templates = LEAGUE_PLAYER_STAT_PAGE_TEMPLATES
    names = categories if categories is not None else list(templates.keys())
    pages = {
        name: (league_stat_path(fbref_comp_id, fbref_slug, templates[name][0], season), templates[name][1])
        for name in names
    }
    return _scrape_player_stat_pages(pages, session, rate_limiter)


def scrape_league_squad_stats(
    fbref_comp_id: str,
    fbref_slug: str,
    session: Optional[requests.Session] = None,
    rate_limiter: Optional[RateLimiter] = None,
    season: Optional[str] = None,
) -> pd.DataFrame:
    """Scrape a single league's squad (team) standard stats table.

    `season` (e.g. "2023-2024"): if given, scrapes that historical season's
    page instead of the current season.
    """
    session = session or requests.Session()
    rate_limiter = rate_limiter or build_rate_limiter(session)
    stat_type, table_id = LEAGUE_SQUAD_STATS_PAGE_TEMPLATE
    path = league_stat_path(fbref_comp_id, fbref_slug, stat_type, season)
    return _scrape_squad_stats_page(path, table_id, session, rate_limiter)


def scrape_team_match_log(
    team_fbref_id: str,
    team_slug: str,
    season: str,
    session: Optional[requests.Session] = None,
    rate_limiter: Optional[RateLimiter] = None,
) -> pd.DataFrame:
    """Scrape a single team's "Scores & Fixtures" match log for a season.

    `team_fbref_id` and `team_slug` come from `api/pipeline/teams.json`
    (see docs/FBREF_PIPELINE.md for how to find these on fbref.com).
    """
    session = session or requests.Session()
    rate_limiter = rate_limiter or build_rate_limiter(session)

    path = f"/en/squads/{team_fbref_id}/{season}/matchlogs/all_comps/schedule/{team_slug}-Scores-and-Fixtures-All-Competitions"
    html = fetch_html(path, session, rate_limiter)
    if html is None:
        return pd.DataFrame()
    table = extract_table(html, "matchlogs_for")
    if table is None:
        return pd.DataFrame()
    table = flatten_columns(table)
    if "Date" in table.columns:
        table = table[table["Date"].notna() & (table["Date"] != "Date")].reset_index(drop=True)
    return table
