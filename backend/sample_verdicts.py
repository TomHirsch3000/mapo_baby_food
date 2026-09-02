#!/usr/bin/env python3
"""
sample_verdicts.py — Pull a readable sample of re-judged pairs for a human.

A uniformly random sample is the wrong tool here. 46% of re-judged pairs are
"mistral said something, qwen3 said neutral", so ten random rows show that one
pattern seven times and the interesting cases not at all. The information is in
the ways the two models diverge, and those are different questions:

  REVERSAL          one says supports, the other refutes. Someone is plainly
                    wrong, and which one tells you whether the complement
                    handling actually improved.
  hard -> neutral   the big bucket, and the open question. Is qwen3 correctly
                    declining on a paper that does not test the claim, or
                    dodging one that does? These two look identical in the data
                    and only a reader can separate them.
  neutral -> hard   rare, and the mirror test: qwen3 finding a verdict mistral
                    missed. If these are mostly right, qwen3 is not simply more
                    timid.
  agreement         a control. If the rows both models agree on look wrong,
                    the problem is upstream of either model.

Stratified, seeded, and written as a CSV with the abstract on the row, so the
adjudication needs nothing but the file.

    python backend/sample_verdicts.py --per-bucket 3
    python backend/sample_verdicts.py --claim back_to_sleep
"""

import argparse
import csv
import os
import random
import sqlite3
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import console
from claims import CLAIMS, tested_text

console.init()

ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
DB_PATH = os.path.join(ROOT, "data", "claims.db")
DEFAULT_OUT = os.path.join(ROOT, "gold", "verdict_sample.csv")

HARD = ("supports", "refutes", "mixed")

# Seeded so the same sample comes back on a re-run and any notes you added
# still line up with the rows they were about.
SEED = 20260902


def bucket(old, new):
    if {old, new} == {"supports", "refutes"}:
        return "REVERSAL"
    if old in HARD and new == "neutral":
        return "hard -> neutral"
    if old == "neutral" and new in HARD:
        return "neutral -> hard"
    if old == new and old in HARD:
        return "agreement (hard)"
    if old == new == "neutral":
        return "agreement (neutral)"
    return "other"


BUCKETS = ("REVERSAL", "hard -> neutral", "neutral -> hard",
           "agreement (hard)", "agreement (neutral)")


def main():
    p = argparse.ArgumentParser(description="Stratified sample of re-judged pairs")
    p.add_argument("--db", default=DB_PATH)
    p.add_argument("--out", default=DEFAULT_OUT)
    p.add_argument("--per-bucket", type=int, default=2)
    p.add_argument("--claim", help="restrict to one claim")
    args = p.parse_args()

    conn = sqlite3.connect(args.db, timeout=30)
    where = "AND q.claim_key = ?" if args.claim else ""
    rows = conn.execute(f"""
        SELECT q.claim_key, q.paperId, p.title, p.abstract, p.cited_by_count,
               m.stance, m.confidence, m.finding,
               q.stance, q.confidence, q.finding, q.evaluated_by
          FROM claim_papers q
          JOIN eval_mistral_202608 m USING(claim_key, paperId)
          JOIN papers p ON p.paperId = q.paperId
         WHERE q.evaluated_by IN ('qwen3-8b-gpu','qwen3:8b')
           AND m.stance IS NOT NULL AND m.stance != '' {where}""",
        (args.claim,) if args.claim else ()).fetchall()

    by = {b: [] for b in BUCKETS}
    for r in rows:
        b = bucket(r[5], r[8])
        if b in by:
            by[b].append(r)

    rng = random.Random(SEED)
    picked = []
    for b in BUCKETS:
        pool = by[b]
        # Prefer well-cited papers: a disputed verdict on a paper nobody cites
        # moves the map less, and is less worth a person's attention.
        pool.sort(key=lambda r: -(r[4] or 0))
        top = pool[:max(args.per_bucket * 8, 20)]
        picked += [(b, r) for r in rng.sample(top, min(args.per_bucket, len(top)))]

    out = []
    for b, r in picked:
        (key, pid, title, abstract, cites,
         m_st, m_conf, m_find, q_st, q_conf, q_find, who) = r
        out.append({
            "bucket": b,
            "claim_key": key,
            "claim_as_judged": tested_text(key) if key in CLAIMS else "(claim dropped)",
            "title": title,
            "citations": cites,
            "mistral_stance": m_st,
            "mistral_confidence": m_conf,
            "mistral_finding": m_find or "",
            "new_stance": q_st,
            "new_confidence": q_conf,
            "new_finding": q_find or "",
            "new_model": who,
            "WHO_IS_RIGHT": "",      # for you: mistral | new | neither | unclear
            "YOUR_NOTES": "",
            "paperId": pid,
            "abstract": abstract or "",
        })

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    # utf-8-sig or Excel reads the curly quotes in abstracts as mojibake.
    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)

    print(f"{args.out}  ({len(out)} rows)\n")
    print(f"  {'bucket':<20} {'pool':>6}   sampled")
    for b in BUCKETS:
        print(f"  {b:<20} {len(by[b]):>6,}   {sum(1 for x, _ in picked if x == b)}")
    print("\n  Fill WHO_IS_RIGHT with: mistral | new | neither | unclear")
    print("  The abstract is the last column, so it settles the row without")
    print("  leaving the file.")


if __name__ == "__main__":
    main()
