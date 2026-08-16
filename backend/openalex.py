#!/usr/bin/env python3
"""
openalex.py — Shared OpenAlex API client.

Single home for the request/retry/budget logic that used to be copy-pasted
between import_openalex.py and import_foods.py.

Public surface:
    BudgetExhaustedError    raised when the daily credit budget is gone
    get_with_retry(url, params)
    count_works(query, filters=None)
    fetch_works(query, max_results, filters=None, select=None)
    reconstruct_abstract(inverted_index)
    parse_authorships(work)
"""

import os
import time

import requests

OPENALEX_BASE = "https://api.openalex.org"
EMAIL = os.environ.get("OPENALEX_EMAIL", "tom.hirsch3000@gmail.com")

# Filters applied to every works query — we only ever want real articles we can read.
BASE_FILTERS = ["type:article", "has_abstract:true"]

DEFAULT_SELECT = (
    "id,title,abstract_inverted_index,publication_year,publication_date,"
    "cited_by_count,authorships,primary_location,referenced_works,topics,type"
)

HARD_PAUSE_AFTER = 4    # after this many fast retries, switch to a long pause
HARD_PAUSE_SECS = 180   # 3 minutes
PAGE_SLEEP_SECS = 0.5   # polite pool allows ~2 req/s; stay well under


class BudgetExhaustedError(Exception):
    """Raised when the OpenAlex daily credit budget is exhausted."""

    def __init__(self, retry_after_secs):
        self.retry_after_secs = retry_after_secs
        hrs = retry_after_secs / 3600
        super().__init__(
            f"OpenAlex daily budget exhausted. Resets in {retry_after_secs}s "
            f"({hrs:.1f}h). Run again after midnight UTC."
        )


def _headers():
    return {"User-Agent": f"mapo-baby-food/1.0 (mailto:{EMAIL})"}


def _params_with_email(params):
    """OpenAlex routes requests with a real mailto to the high-rate polite pool."""
    return {**params, "mailto": EMAIL}


def _parse_429(response):
    """Extract (is_budget_exhausted, wait_seconds) from a 429 response."""
    # OpenAlex budget errors carry retryAfter in the JSON body
    try:
        body = response.json()
        if "dailyRemainingUsd" in body or "creditsRemaining" in body:
            return True, int(body.get("retryAfter", 3600))
        body_wait = body.get("retryAfter")
        if body_wait:
            return False, int(body_wait)
    except Exception:
        pass

    header = response.headers.get("Retry-After")
    if header:
        try:
            value = int(header)
            # Unix timestamps are > 1 billion; durations are not
            wait = max(1, value - int(time.time())) if value > 1_000_000_000 else value
            return False, min(wait, 120)
        except ValueError:
            pass

    return False, 0


def get_with_retry(url, params, max_retries=8, base_delay=5):
    """GET with retries on 429/5xx.

    attempts 1-4 : exponential back-off (5s, 10s, 20s, 40s)
    attempts 5-8 : hard 3-minute pause each time
    Budget exhaustion raises BudgetExhaustedError immediately — retrying cannot help.
    """
    r = None
    for attempt in range(max_retries):
        r = requests.get(url, params=_params_with_email(params),
                         headers=_headers(), timeout=30)

        if r.status_code == 429:
            is_budget, wait_secs = _parse_429(r)
            if is_budget:
                raise BudgetExhaustedError(wait_secs)
            if attempt < HARD_PAUSE_AFTER:
                wait = max(wait_secs, base_delay * (2 ** attempt))
                print(f"\n  [rate-limit] 429 — waiting {wait}s "
                      f"(attempt {attempt + 1}/{max_retries})...")
            else:
                wait = HARD_PAUSE_SECS
                print(f"\n  [rate-limit] 429 — hard pause {wait}s "
                      f"({attempt + 1}/{max_retries})...")
            time.sleep(wait)
            continue

        if r.status_code >= 500 and attempt < max_retries - 1:
            wait = base_delay * (2 ** min(attempt, HARD_PAUSE_AFTER - 1))
            print(f"\n  [server-error] {r.status_code} — waiting {wait}s...")
            time.sleep(wait)
            continue

        r.raise_for_status()
        return r

    r.raise_for_status()
    return r


def _build_filter(extra_filters=None):
    filters = list(BASE_FILTERS)
    if extra_filters:
        filters.extend(extra_filters)
    return ",".join(filters)


def count_works(query, extra_filters=None):
    """Total number of OpenAlex works matching a query. One cheap call."""
    params = {
        "search": query,
        "filter": _build_filter(extra_filters),
        "per-page": 1,
        "select": "id",
    }
    try:
        resp = get_with_retry(f"{OPENALEX_BASE}/works", params)
        return resp.json().get("meta", {}).get("count", 0)
    except BudgetExhaustedError:
        raise
    except Exception as e:
        print(f"  [warn] count fetch failed for '{query}': {e}")
        return 0


def fetch_works(query, max_results=200, extra_filters=None, select=None, quiet=False):
    """Cursor-paginated fetch from /works. Returns at most max_results raw works."""
    params = {
        "search": query,
        "filter": _build_filter(extra_filters),
        "per-page": min(200, max_results),
        "cursor": "*",
        "select": select or DEFAULT_SELECT,
    }

    fetched = []
    while len(fetched) < max_results:
        resp = get_with_retry(f"{OPENALEX_BASE}/works", params)
        data = resp.json()
        results = data.get("results", [])
        if not results:
            break
        fetched.extend(results)
        if not quiet:
            print(f"  Fetched {len(fetched)} papers...", end="\r")
        cursor = data.get("meta", {}).get("next_cursor")
        if not cursor:
            break
        params["cursor"] = cursor
        time.sleep(PAGE_SLEEP_SECS)

    if not quiet:
        print(f"  Fetched {len(fetched)} papers total.   ")
    return fetched[:max_results]


def reconstruct_abstract(inverted_index):
    """OpenAlex ships abstracts as {word: [positions]}. Rebuild the prose."""
    if not inverted_index:
        return ""
    positions = {}
    for word, pos_list in inverted_index.items():
        for pos in pos_list:
            positions[pos] = word
    return " ".join(positions[k] for k in sorted(positions))


def parse_authorships(work):
    """Return (all_author_names, first_author_name, all_institution_names)."""
    authorships = work.get("authorships", [])
    names = [
        a["author"]["display_name"]
        for a in authorships
        if a.get("author") and a["author"].get("display_name")
    ]
    institutions = []
    for a in authorships:
        for inst in a.get("institutions", []):
            display = inst.get("display_name")
            if display and display not in institutions:
                institutions.append(display)
    return "; ".join(names), (names[0] if names else ""), "; ".join(institutions)


def work_id(work):
    """Strip the URL prefix off an OpenAlex work id."""
    return work["id"].replace("https://openalex.org/", "")
