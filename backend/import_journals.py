#!/usr/bin/env python3
"""
import_journals.py — Attach a journal-quality metric to every paper.

Where a paper was published is part of how much weight it deserves, and nothing
in the pipeline knew it: the corpus stored a venue NAME and no identifier, so
"Development and Psychopathology" was a string and not a journal with a track
record.

The metric is OpenAlex's summary_stats.2yr_mean_citedness - mean citations over
the prior two years, which is the definition a journal impact factor uses. It is
free, covers everything OpenAlex indexes, and needs no licence, which the real
JIF does. h-index comes along for free in the same payload.

Two passes, both resumable and both batched a hundred at a time:

    1. papers -> source id   (works?filter=openalex_id:W..|W..)
    2. source id -> stats    (sources?filter=openalex_id:S..|S..)

Usage:
    python backend/import_journals.py
    python backend/import_journals.py --limit 500
    python backend/import_journals.py --refresh-sources
"""

import argparse
import os
import sqlite3
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import console
import openalex

console.init()

DATA_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "claims.db")

BATCH = 100          # OpenAlex takes up to 100 ids in one filter


def ensure_schema(conn):
    cols = {r[1] for r in conn.execute("PRAGMA table_info(papers)").fetchall()}
    if "source_id" not in cols:
        conn.execute("ALTER TABLE papers ADD COLUMN source_id TEXT")
    # A paper with no journal is not an error - preprints, book chapters and
    # reports all legitimately have none - so record that we looked rather than
    # retrying them on every run.
    if "source_checked_at" not in cols:
        conn.execute("ALTER TABLE papers ADD COLUMN source_checked_at TEXT")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS sources (
            source_id       TEXT PRIMARY KEY,
            display_name    TEXT,
            type            TEXT,
            works_count     INTEGER,
            impact          REAL,     -- 2yr_mean_citedness, the JIF equivalent
            h_index         INTEGER,
            i10_index       INTEGER,
            fetched_at      TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_papers_source ON papers(source_id)")
    conn.commit()


def short_id(url_or_id):
    return (url_or_id or "").rsplit("/", 1)[-1] or None


def fetch_paper_sources(conn, limit=None):
    """Pass 1: which journal each paper appeared in."""
    rows = conn.execute("""
        SELECT paperId FROM papers
        WHERE source_checked_at IS NULL
        ORDER BY cited_by_count DESC
    """).fetchall()
    if limit:
        rows = rows[:limit]
    if not rows:
        print("Every paper already has its source resolved.")
        return 0

    ids = [r[0] for r in rows]
    print(f"Resolving the journal for {len(ids)} papers, {BATCH} at a time...")
    done = matched = 0
    started = time.time()

    for i in range(0, len(ids), BATCH):
        chunk = ids[i:i + BATCH]
        resp = openalex.get_with_retry(
            f"{openalex.OPENALEX_BASE}/works",
            {"filter": f"openalex_id:{'|'.join(chunk)}",
             "select": "id,primary_location",
             "per-page": BATCH})
        results = resp.json().get("results", [])

        seen = set()
        for w in results:
            pid = short_id(w.get("id"))
            seen.add(pid)
            src = (w.get("primary_location") or {}).get("source") or {}
            conn.execute(
                "UPDATE papers SET source_id = ?, source_checked_at = datetime('now') "
                "WHERE paperId = ?",
                (short_id(src.get("id")), pid))
            if src.get("id"):
                matched += 1

        # A paper OpenAlex no longer returns still counts as checked, or it is
        # re-requested on every future run for ever.
        for pid in chunk:
            if pid not in seen:
                conn.execute(
                    "UPDATE papers SET source_checked_at = datetime('now') WHERE paperId = ?",
                    (pid,))
        conn.commit()

        done += len(chunk)
        rate = (time.time() - started) / max(1, done)
        eta = rate * (len(ids) - done)
        print(f"  [{done}/{len(ids)}] {matched} with a journal  ETA {eta/60:.1f}m")

    return matched


def fetch_source_stats(conn, refresh=False):
    """Pass 2: the impact metric for each distinct journal."""
    if refresh:
        rows = conn.execute(
            "SELECT DISTINCT source_id FROM papers WHERE source_id IS NOT NULL").fetchall()
    else:
        rows = conn.execute("""
            SELECT DISTINCT p.source_id FROM papers p
            LEFT JOIN sources s USING(source_id)
            WHERE p.source_id IS NOT NULL AND s.source_id IS NULL
        """).fetchall()
    ids = [r[0] for r in rows]
    if not ids:
        print("Every journal already has its stats.")
        return 0

    print(f"\nFetching stats for {len(ids)} journals...")
    done = 0
    for i in range(0, len(ids), BATCH):
        chunk = ids[i:i + BATCH]
        resp = openalex.get_with_retry(
            f"{openalex.OPENALEX_BASE}/sources",
            {"filter": f"openalex_id:{'|'.join(chunk)}",
             "select": "id,display_name,type,works_count,summary_stats",
             "per-page": BATCH})
        for s in resp.json().get("results", []):
            stats = s.get("summary_stats") or {}
            conn.execute("""
                INSERT INTO sources (source_id, display_name, type, works_count,
                                     impact, h_index, i10_index, fetched_at)
                VALUES (?,?,?,?,?,?,?, datetime('now'))
                ON CONFLICT(source_id) DO UPDATE SET
                    display_name=excluded.display_name, type=excluded.type,
                    works_count=excluded.works_count, impact=excluded.impact,
                    h_index=excluded.h_index, i10_index=excluded.i10_index,
                    fetched_at=excluded.fetched_at
            """, (short_id(s.get("id")), s.get("display_name"), s.get("type"),
                  s.get("works_count"), stats.get("2yr_mean_citedness"),
                  stats.get("h_index"), stats.get("i10_index")))
        conn.commit()
        done += len(chunk)
        print(f"  [{done}/{len(ids)}] journals")
    return done


def main():
    parser = argparse.ArgumentParser(description="Journal impact metrics from OpenAlex")
    parser.add_argument("--limit", type=int, help="max papers to resolve this run")
    parser.add_argument("--refresh-sources", action="store_true",
                        help="re-fetch stats for journals already stored")
    parser.add_argument("--db", default=DB_PATH)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    ensure_schema(conn)
    try:
        fetch_paper_sources(conn, limit=args.limit)
        fetch_source_stats(conn, refresh=args.refresh_sources)

        cov = conn.execute("""
            SELECT COUNT(*),
                   SUM(CASE WHEN p.source_id IS NOT NULL THEN 1 ELSE 0 END),
                   SUM(CASE WHEN s.impact IS NOT NULL THEN 1 ELSE 0 END)
            FROM papers p LEFT JOIN sources s USING(source_id)
        """).fetchone()
        print(f"\n{cov[1]}/{cov[0]} papers have a journal; "
              f"{cov[2]} have an impact metric.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
