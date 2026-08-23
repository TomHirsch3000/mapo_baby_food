#!/usr/bin/env python3
"""
restore_stances.py — Re-seed claims.db stances from the committed evidence JSON.

data/claims.db is git-ignored, so a fresh clone (or a second machine) starts
with no stances at all. The JSON under frontend/public/claims IS committed, and
it already carries every field evaluate_claims.py writes. Re-judging those pairs
would cost hours of local inference to reproduce answers we already published --
and, because a different mistral build can score an abstract differently, it
would quietly churn stances that are already live on the map.

So: pull the stances back out of the JSON first, then let evaluate_claims.py
handle only what is genuinely new.

This is also what makes the work portable. data/claims.db never leaves the
machine that built it, but every verdict AND the reasoning behind it round-trips
through committed JSON, so a second machine reaches the same state with

    import_claims.py --all --skip-done     # papers back from OpenAlex
    restore_stances.py                     # verdicts + reasoning back from git
    evaluate_claims.py --all --stale       # only what git did not already have

Usage:
    python backend/restore_stances.py
    python backend/restore_stances.py --dry-run
    python backend/restore_stances.py --overwrite   # trust JSON over the DB
"""

import argparse
import json
import os
import sqlite3
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import console

console.init()

DATA_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "claims.db")
CLAIMS_DIR = os.path.normpath(
    os.path.join(SCRIPT_DIR, "..", "frontend", "public", "claims")
)

# build_claims_data.py writes an unjudged paper out as the literal string
# "unevaluated", which is truthy - so a naive `if paper["stance"]` restores it as
# though it were a verdict, and every downstream tally then trips over a category
# it has no bucket for. Only these four are real.
REAL_STANCES = {"supports", "refutes", "neutral", "mixed"}

# evidence.json field -> claim_papers column
FIELD_MAP = {
    "stance": "stance",
    "confidence": "confidence",
    "stanceSummary": "stance_summary",
    "evidenceStrength": "evidence_strength",
    "studyType": "study_type",
    # The reasoning matters most of all here: it is the only part of a verdict
    # that cannot be re-derived without paying for inference again, and it is
    # what makes a restored verdict auditable rather than just present.
    "finding": "finding",
    "direction": "direction",
}


def iter_evidence(claims_dir):
    """Yield (claim_key, paper_record) for every evaluated paper in the JSON."""
    for topic in sorted(os.listdir(claims_dir)):
        topic_dir = os.path.join(claims_dir, topic)
        if not os.path.isdir(topic_dir):
            continue
        for claim_key in sorted(os.listdir(topic_dir)):
            path = os.path.join(topic_dir, claim_key, "evidence.json")
            if not os.path.isfile(path):
                continue
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            for paper in data.get("papers", []):
                if paper.get("stance") in REAL_STANCES:
                    yield claim_key, paper


def restore(db_path, claims_dir, overwrite=False, dry_run=False):
    conn = sqlite3.connect(db_path, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")

    restored = already = absent = 0
    per_claim = {}

    for claim_key, paper in iter_evidence(claims_dir):
        paper_id = paper.get("id")
        if not paper_id:
            continue

        row = conn.execute(
            "SELECT stance FROM claim_papers WHERE claim_key = ? AND paperId = ?",
            (claim_key, paper_id),
        ).fetchone()

        if row is None:
            # Published previously, but this claim's current OpenAlex query no
            # longer returns it. Nothing to attach the stance to.
            absent += 1
            continue
        if row[0] and not overwrite:
            already += 1
            continue

        if not dry_run:
            conn.execute(
                """
                UPDATE claim_papers
                   SET stance = ?, confidence = ?, stance_summary = ?,
                       evidence_strength = ?, study_type = ?,
                       finding = ?, direction = ?,
                       evaluated_at = COALESCE(evaluated_at, datetime('now'))
                 WHERE claim_key = ? AND paperId = ?
                """,
                (
                    paper.get("stance"),
                    paper.get("confidence"),
                    paper.get("stanceSummary"),
                    paper.get("evidenceStrength"),
                    paper.get("studyType"),
                    paper.get("finding"),
                    paper.get("direction"),
                    claim_key,
                    paper_id,
                ),
            )
        restored += 1
        per_claim[claim_key] = per_claim.get(claim_key, 0) + 1

    if dry_run:
        conn.rollback()
    else:
        conn.commit()

    for key in sorted(per_claim, key=lambda k: -per_claim[k]):
        print(f"  {key:30s} {per_claim[key]:4d} stances restored")

    pending = conn.execute(
        "SELECT COUNT(*) FROM claim_papers WHERE stance IS NULL OR stance = ''"
    ).fetchone()[0]
    conn.close()

    verb = "would restore" if dry_run else "restored"
    print(f"\n{verb} {restored}; {already} already had a stance; "
          f"{absent} published papers are no longer linked to their claim.")
    print(f"{pending} pair(s) still need evaluate_claims.py.")
    return restored


def main():
    parser = argparse.ArgumentParser(
        description="Re-seed claims.db stances from committed evidence JSON")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--claims-dir", default=CLAIMS_DIR)
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would change, write nothing")
    parser.add_argument("--overwrite", action="store_true",
                        help="replace stances the DB already holds")
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"[error] {args.db} not found - run import_claims.py first")
        raise SystemExit(1)

    restore(args.db, args.claims_dir, overwrite=args.overwrite, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
