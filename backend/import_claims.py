#!/usr/bin/env python3
"""
import_claims.py — Collect papers per CLAIM from OpenAlex into data/claims.db.

Unlike the old topic importer, the unit of collection is the claim: each claim
runs its own tuned OpenAlex query, so a paper lands in the DB because it speaks
to that claim.

One paper can be evidence for several claims, so papers are deduped into a
single `papers` table and linked through `claim_papers`.

Usage:
    python backend/import_claims.py --seed                  # small proof run
    python backend/import_claims.py --all                   # every claim
    python backend/import_claims.py peanut_introduction     # a subject
    python backend/import_claims.py sleep --max-results 300 # a whole domain
"""

import argparse
import json
import os
import sqlite3
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import console
import openalex as oa
from claims import CLAIMS, TOPICS, resolve_claim_keys

console.init()

DATA_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "claims.db")


# ── Schema ───────────────────────────────────────────────────────────────────

def create_db(db_path=DB_PATH):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS papers (
            paperId              TEXT PRIMARY KEY,
            title                TEXT,
            abstract             TEXT,
            year                 INTEGER,
            publicationDate      TEXT,
            cited_by_count       INTEGER DEFAULT 0,
            all_author_names     TEXT,
            first_author_name    TEXT,
            all_institution_names TEXT,
            venue                TEXT,
            doi                  TEXT,
            url                  TEXT
        );

        CREATE TABLE IF NOT EXISTS claim_papers (
            claim_key       TEXT,
            paperId         TEXT,
            keyword_score   INTEGER DEFAULT 0,
            stance          TEXT,           -- supports | refutes | neutral | mixed
            confidence      INTEGER,        -- 0-100
            stance_summary  TEXT,
            evidence_strength TEXT,         -- strong | moderate | limited | mixed
            study_type      TEXT,
            finding         TEXT,           -- the model's restatement of the result
            direction       TEXT,           -- agrees | disagrees | both | does not test it
            evaluated_at    TEXT,
            PRIMARY KEY (claim_key, paperId)
        );

        CREATE TABLE IF NOT EXISTS citations (
            source TEXT,
            target TEXT,
            PRIMARY KEY (source, target)
        );

        CREATE TABLE IF NOT EXISTS claim_meta (
            claim_key       TEXT PRIMARY KEY,
            openalex_count  INTEGER DEFAULT 0,
            imported_count  INTEGER DEFAULT 0,
            fetched_at      TEXT
        );


        CREATE INDEX IF NOT EXISTS idx_claim_papers_claim  ON claim_papers(claim_key);
        CREATE INDEX IF NOT EXISTS idx_claim_papers_stance ON claim_papers(claim_key, stance);
        CREATE INDEX IF NOT EXISTS idx_papers_cited        ON papers(cited_by_count DESC);
    """)
    conn.commit()
    return conn


# ── Parsing ──────────────────────────────────────────────────────────────────

def parse_paper(work):
    """OpenAlex work -> (paper dict, referenced work ids)."""
    all_authors, first_author, institutions = oa.parse_authorships(work)
    location = work.get("primary_location") or {}
    source = location.get("source") or {}

    doi = work.get("doi") or ""
    paper = {
        "paperId": oa.work_id(work),
        "title": work.get("title") or "",
        "abstract": oa.reconstruct_abstract(work.get("abstract_inverted_index")),
        "year": work.get("publication_year"),
        "publicationDate": work.get("publication_date") or "",
        "cited_by_count": work.get("cited_by_count", 0) or 0,
        "all_author_names": all_authors,
        "first_author_name": first_author,
        "all_institution_names": institutions,
        "venue": source.get("display_name") or "",
        "doi": doi,
        "url": location.get("landing_page_url") or doi or "",
    }
    refs = [r.replace("https://openalex.org/", "") for r in work.get("referenced_works", [])]
    return paper, refs


def keyword_score(claim_cfg, title, abstract):
    """How many of the claim's keyword hints appear. Cheap relevance pre-filter."""
    text = f"{title or ''} {abstract or ''}".lower()
    return sum(1 for kw in claim_cfg["keyword_hints"] if kw.lower() in text)


# ── Import ───────────────────────────────────────────────────────────────────

UPSERT_PAPER = """
    INSERT INTO papers (paperId, title, abstract, year, publicationDate,
                        cited_by_count, all_author_names, first_author_name,
                        all_institution_names, venue, doi, url)
    VALUES (:paperId, :title, :abstract, :year, :publicationDate,
            :cited_by_count, :all_author_names, :first_author_name,
            :all_institution_names, :venue, :doi, :url)
    ON CONFLICT(paperId) DO UPDATE SET
        cited_by_count = excluded.cited_by_count,
        abstract = CASE WHEN length(excluded.abstract) > length(papers.abstract)
                        THEN excluded.abstract ELSE papers.abstract END
"""


def record_claim_count(conn, claim_key, total):
    conn.execute("""
        INSERT INTO claim_meta (claim_key, openalex_count, fetched_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(claim_key) DO UPDATE SET
            openalex_count = excluded.openalex_count,
            fetched_at     = excluded.fetched_at
    """, (claim_key, total))


def fetch_counts(conn, claim_keys, refresh=False):
    """Populate OpenAlex match counts without importing any papers.

    This is what lets an un-researched claim still appear on the map at its
    true size: node area comes from these counts, not from collected papers.
    """
    existing = {}
    if not refresh:
        existing = {
            r[0]: r[1] for r in conn.execute(
                "SELECT claim_key, openalex_count FROM claim_meta "
                "WHERE openalex_count > 0").fetchall()
        }

    todo = [k for k in claim_keys if k not in existing]
    print(f"Fetching counts for {len(todo)} claim(s) "
          f"({len(claim_keys) - len(todo)} already known)\n")

    for i, key in enumerate(todo, 1):
        cfg = CLAIMS[key]
        total = oa.count_works(cfg["query"])
        record_claim_count(conn, key, total)
        conn.commit()
        print(f"  [{i:3d}/{len(todo)}] {key:32s} {total:>9,d}")
        time.sleep(oa.PAGE_SLEEP_SECS)


def import_claim(conn, claim_key, max_results=200, min_keyword_score=1):
    cfg = CLAIMS[claim_key]
    topic = TOPICS[cfg["topic"]]["name"]

    print(f"\n[claim] {claim_key}")
    print(f"        {topic} / {cfg['group']}")
    print(f"        \"{cfg['claim']}\"")
    print(f"        query: {cfg['query']}")

    # One request, not two: the fetch response carries meta.count, and OpenAlex
    # bills a flat 10 credits per request whatever it returns. A separate
    # count_works() call here used to cost exactly as much as the fetch itself,
    # halving how many claims a day's budget could import.
    works, total = oa.fetch_works(cfg["query"], max_results=max_results,
                                  with_count=True)
    print(f"        {total:,} works in OpenAlex")

    known_before = {r[0] for r in conn.execute("SELECT paperId FROM papers").fetchall()}
    linked = skipped = new_papers = 0
    citation_pairs = []

    for work in works:
        paper, refs = parse_paper(work)
        if not paper["title"] or not paper["abstract"]:
            skipped += 1
            continue

        score = keyword_score(cfg, paper["title"], paper["abstract"])
        if score < min_keyword_score:
            # Query matched but the abstract does not discuss the claim's concepts.
            skipped += 1
            continue

        conn.execute(UPSERT_PAPER, paper)
        if paper["paperId"] not in known_before:
            known_before.add(paper["paperId"])
            new_papers += 1

        conn.execute("""
            INSERT INTO claim_papers (claim_key, paperId, keyword_score)
            VALUES (?, ?, ?)
            ON CONFLICT(claim_key, paperId) DO UPDATE SET keyword_score = excluded.keyword_score
        """, (claim_key, paper["paperId"], score))
        linked += 1

        citation_pairs.extend((paper["paperId"], ref) for ref in refs)

    # Keep only citations where both ends are papers we actually hold.
    known = {r[0] for r in conn.execute("SELECT paperId FROM papers").fetchall()}
    citations = 0
    for src, tgt in citation_pairs:
        if tgt in known:
            conn.execute("INSERT OR IGNORE INTO citations (source, target) VALUES (?, ?)",
                         (src, tgt))
            citations += 1

    conn.execute("""
        INSERT INTO claim_meta (claim_key, openalex_count, imported_count, fetched_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(claim_key) DO UPDATE SET
            openalex_count = excluded.openalex_count,
            imported_count = excluded.imported_count,
            fetched_at     = excluded.fetched_at
    """, (claim_key, total, linked))
    conn.commit()

    print(f"        linked {linked} papers ({new_papers} new), "
          f"{skipped} skipped, {citations} citations")
    return linked


def main():
    parser = argparse.ArgumentParser(
        description="Import papers per claim from OpenAlex")
    parser.add_argument("selection", nargs="*",
                        help="claim / topic keys (default: all)")
    parser.add_argument("--seed", action="store_true",
                        help="import the small cross-topic proof set")
    parser.add_argument("--all", action="store_true", help="import every claim")
    parser.add_argument("--counts-only", action="store_true",
                        help="fetch OpenAlex match counts only; import no papers")
    parser.add_argument("--refresh-counts", action="store_true",
                        help="re-fetch counts that are already stored")
    parser.add_argument("--max-results", type=int, default=200,
                        help="papers to fetch per claim (default 200)")
    parser.add_argument("--min-keyword-score", type=int, default=1,
                        help="minimum keyword hints required to keep a paper")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--list", action="store_true", help="list claims and exit")
    parser.add_argument("--skip-done", action="store_true",
                        help="skip claims that already have papers (resume a "
                             "budget-interrupted run without re-paying for them)")
    args = parser.parse_args()

    if args.list:
        for key, cfg in CLAIMS.items():
            print(f"  {key:32s} {TOPICS[cfg['topic']]['name']:18s} {cfg['claim']}")
        return

    try:
        keys = resolve_claim_keys(args.selection or None, seed=args.seed)
    except KeyError as e:
        print(f"[error] {e}")
        raise SystemExit(1)

    if not args.selection and not args.seed and not args.all and not args.counts_only:
        print("[error] pass --seed, --all, --counts-only, or claim/topic keys")
        raise SystemExit(1)

    conn = create_db(args.db)

    if args.counts_only:
        try:
            fetch_counts(conn, keys, refresh=args.refresh_counts)
        except oa.BudgetExhaustedError as e:
            print(f"\n[stop] {e}")
        finally:
            conn.close()
        return

    if args.skip_done:
        already = {r[0] for r in conn.execute(
            "SELECT DISTINCT claim_key FROM claim_papers").fetchall()}
        skipped = [k for k in keys if k in already]
        keys = [k for k in keys if k not in already]
        if skipped:
            print(f"Skipping {len(skipped)} claim(s) already imported.")

    if not keys:
        print("Nothing to import - every selected claim already has papers.")
        conn.close()
        return

    print(f"Importing {len(keys)} claim(s) into {args.db}")
    total_linked = 0
    try:
        for i, key in enumerate(keys, 1):
            print(f"\n=== [{i}/{len(keys)}] ===")
            try:
                total_linked += import_claim(
                    conn, key,
                    max_results=args.max_results,
                    min_keyword_score=args.min_keyword_score,
                )
            except oa.BudgetExhaustedError as e:
                print(f"\n[stop] {e}")
                break
            time.sleep(oa.PAGE_SLEEP_SECS)
    finally:
        papers = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        links = conn.execute("SELECT COUNT(*) FROM claim_papers").fetchone()[0]
        conn.close()
        print(f"\nDone. {papers} unique papers, {links} claim-paper links.")


if __name__ == "__main__":
    main()
