#!/usr/bin/env python3
"""
apply_verdicts.py — Write externally-produced stance verdicts into claims.db.

evaluate_claims.py judges pairs with a local model and writes them in one step.
When the judging happens elsewhere - a frontier model called from a session, a
batch job, a human review pass - the verdicts still have to land in the same
columns, pass the same validation, and be recorded the same way. This is that
half of the job on its own.

Input is a JSON list of objects using the evaluator's own field names, so a
verdict produced by either path is the same shape:

    [{"paperId": "W123", "finding": ..., "direction": ..., "stance": ...,
      "confidence": 0-100, "summary": ..., "evidence_strength": ...,
      "study_type": ...}, ...]

Usage:
    python backend/apply_verdicts.py crawling_not_required verdicts.json
    python backend/apply_verdicts.py crawling_not_required verdicts.json --dry-run
"""

import argparse
import json
import os
import sqlite3
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from evaluate_claims import DB_PATH, ensure_schema, validate

UPDATE_SQL = """
    UPDATE claim_papers
       SET stance = ?, confidence = ?, stance_summary = ?,
           evidence_strength = ?, study_type = ?, finding = ?, direction = ?,
           evaluated_at = datetime('now')
     WHERE claim_key = ? AND paperId = ?
"""


def main():
    parser = argparse.ArgumentParser(description="Apply external stance verdicts")
    parser.add_argument("claim_key")
    parser.add_argument("verdicts", help="JSON file of verdict objects")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(args.verdicts) as f:
        verdicts = json.load(f)

    conn = sqlite3.connect(args.db, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    ensure_schema(conn)

    applied = skipped = 0
    for v in verdicts:
        paper_id = v.get("paperId")
        # Same validator as the local path: clamps confidence, matches loose
        # stance wording, and lets `direction` override a keyword-matched stance.
        result = validate(v)
        if not paper_id or not result:
            print(f"  [skip] {paper_id} - unusable verdict")
            skipped += 1
            continue

        # A verdict for a pair that is not in the table is a typo in the paperId,
        # not a new link. Say so rather than silently writing nothing.
        exists = conn.execute(
            "SELECT 1 FROM claim_papers WHERE claim_key = ? AND paperId = ?",
            (args.claim_key, paper_id)).fetchone()
        if not exists:
            print(f"  [skip] {paper_id} - no such (claim, paper) pair")
            skipped += 1
            continue

        if not args.dry_run:
            conn.execute(UPDATE_SQL, (
                result["stance"], result["confidence"], result["stance_summary"],
                result["evidence_strength"], result["study_type"],
                result["finding"], result["direction"],
                args.claim_key, paper_id))
            conn.commit()
        applied += 1
        print(f"  {result['stance']:8s} ({result['confidence']:3d}%) "
              f"{result['evidence_strength']:8s} {paper_id}")

    conn.close()
    verb = "would apply" if args.dry_run else "applied"
    print(f"\n{verb} {applied}, skipped {skipped}")


if __name__ == "__main__":
    main()
