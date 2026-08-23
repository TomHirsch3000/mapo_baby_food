#!/usr/bin/env python3
"""
audit_stances.py — Check stored verdicts against themselves and against a
second opinion.

Two failure modes are worth separating:

  --coherence  Does the stored one-line summary actually justify the stored
               stance? This is cheap (the summary is ~20 words, so inference is
               fast) and catches the worst class of error: a badge saying
               REFUTES above a sentence that plainly supports. Whatever the
               right label is, a record like that is incoherent to a reader, so
               it is a defect regardless of who is right.

  --rejudge    An independent second classification of the same abstract, WITHOUT
               showing the model what was stored. Asking "do you agree with this
               stance?" invites agreement; asking cold and then comparing does
               not. The disagreement rate is a reliability estimate for the map.

Usage:
    python backend/audit_stances.py --coherence --limit 80
    python backend/audit_stances.py --rejudge --limit 40 --claim no_screens_under_2
"""

import argparse
import os
import random
import sqlite3
import sys
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import console
import llm
from claims import CLAIMS, tested_text

console.init()

DATA_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "claims.db")

AUDIT_SYSTEM = (
    "You are auditing a claim-evidence database for internal consistency. "
    "Respond ONLY with valid JSON, no markdown, no commentary."
)

# Deliberately withholds the stored stance. The model classifies the sentence on
# its own terms; the caller compares. Showing it the answer first turns this into
# a leading question.
COHERENCE_PROMPT = """\
CLAIM: "{claim}"

A reviewer wrote this one-line finding about a paper's result on that claim:
"{summary}"

Taking that sentence at face value, does it argue FOR the claim, AGAINST it, or
neither?

Respond with ONLY this JSON:
{{
  "reads_as": "supports | refutes | neither",
  "why": "<max 15 words>"
}}
"""

REJUDGE_PROMPT = """\
CLAIM: "{claim}"

PAPER TITLE: {title}
ABSTRACT: {abstract}

Does this paper's own findings agree or disagree with the CLAIM? Note that a
paper can report harm from a large dose while still showing benefit from a small
or better-quality one; if the abstract cuts both ways, say "mixed".

Respond with ONLY this JSON:
{{
  "finding": "<what the paper concluded, max 20 words>",
  "stance": "supports | refutes | neutral | mixed",
  "confidence": <0-100 integer>,
  "why": "<max 20 words>"
}}
"""

SAMPLE_SQL = """
    SELECT cp.claim_key, cp.paperId, p.title, p.abstract,
           cp.stance, cp.confidence, cp.stance_summary, cp.evidence_strength
    FROM claim_papers cp
    JOIN papers p USING(paperId)
    WHERE cp.stance IS NOT NULL AND cp.stance != ''
      {claim_filter}
    ORDER BY p.cited_by_count DESC
"""


def sample(conn, claim=None, limit=80, seed=7):
    sql = SAMPLE_SQL.format(claim_filter="AND cp.claim_key = ?" if claim else "")
    rows = conn.execute(sql, (claim,) if claim else ()).fetchall()
    # Highest-cited first above, then a stable shuffle: the audit should cover
    # the papers a reader is most likely to click, not a uniform dribble.
    head = rows[: limit * 2]
    random.Random(seed).shuffle(head)
    return head[:limit]


def run_coherence(conn, client, model, rows):
    mismatches = []
    tally = Counter()

    for i, r in enumerate(rows, 1):
        claim_key, paper_id, title, _abstract, stance, conf, summary, strength = r
        if not summary:
            continue
        prompt = COHERENCE_PROMPT.format(
            claim=tested_text(claim_key), summary=summary)
        try:
            out = llm.parse_json_response(
                llm.call_llm(client, model, AUDIT_SYSTEM, prompt,
                             temperature=0.0, max_tokens=120))
        except Exception as e:
            print(f"  [{i}/{len(rows)}] {claim_key} - LLM error: {e}")
            continue
        if not out or "reads_as" not in out:
            continue

        reads = str(out["reads_as"]).strip().lower()
        # "neither" vs "neutral" is not a contradiction worth flagging; a flat
        # inversion between supports and refutes is.
        contradiction = (
            (reads == "supports" and stance == "refutes")
            or (reads == "refutes" and stance == "supports")
        )
        tally[f"{stance}->{reads}"] += 1
        if contradiction:
            mismatches.append({
                "claim_key": claim_key, "paper_id": paper_id, "title": title,
                "stored": stance, "reads_as": reads, "confidence": conf,
                "strength": strength, "summary": summary,
                "why": out.get("why", ""),
            })
            print(f"  [{i}/{len(rows)}] CONTRADICTION  {claim_key}")
            print(f"        stored '{stance}' ({conf}%) but summary reads as '{reads}'")
            print(f"        {(title or '')[:80]}")
            print(f"        \"{summary}\"")
        else:
            print(f"  [{i}/{len(rows)}] ok  {stance:8s} <- reads '{reads}'  {claim_key}")

    return mismatches, tally


def run_rejudge(conn, client, model, rows):
    disagreements = []
    tally = Counter()

    for i, r in enumerate(rows, 1):
        claim_key, paper_id, title, abstract, stance, conf, summary, strength = r
        prompt = REJUDGE_PROMPT.format(
            claim=tested_text(claim_key), title=title,
            abstract=(abstract or "(no abstract)")[:1800])
        try:
            out = llm.parse_json_response(
                llm.call_llm(client, model, AUDIT_SYSTEM, prompt,
                             temperature=0.0, max_tokens=250))
        except Exception as e:
            print(f"  [{i}/{len(rows)}] {claim_key} - LLM error: {e}")
            continue
        if not out or "stance" not in out:
            continue

        second = str(out["stance"]).strip().lower()
        tally[f"{stance}->{second}"] += 1
        flipped = {stance, second} == {"supports", "refutes"}
        if flipped or second == "mixed":
            disagreements.append({
                "claim_key": claim_key, "paper_id": paper_id, "title": title,
                "stored": stance, "second": second, "confidence": conf,
                "finding": out.get("finding", ""), "why": out.get("why", ""),
            })
            flag = "FLIP" if flipped else "MIXED"
            print(f"  [{i}/{len(rows)}] {flag}  {claim_key}: stored '{stance}' vs '{second}'")
            print(f"        {(title or '')[:80]}")
            print(f"        second opinion: {out.get('finding','')}")
        else:
            print(f"  [{i}/{len(rows)}] agree  {stance:8s}  {claim_key}")

    return disagreements, tally


def main():
    parser = argparse.ArgumentParser(description="Audit stored stances")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--claim", help="restrict to one claim key")
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--model", default=None)
    parser.add_argument("--coherence", action="store_true",
                        help="does the stored summary match the stored stance")
    parser.add_argument("--rejudge", action="store_true",
                        help="independent second classification of the abstract")
    args = parser.parse_args()

    if not args.coherence and not args.rejudge:
        print("[error] pass --coherence and/or --rejudge")
        raise SystemExit(1)
    if args.claim and args.claim not in CLAIMS:
        print(f"[error] unknown claim '{args.claim}'")
        raise SystemExit(1)

    conn = sqlite3.connect(args.db, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    client, model = llm.get_client(model=args.model)
    rows = sample(conn, claim=args.claim, limit=args.limit)
    print(f"Auditing {len(rows)} stored verdict(s) with {model}\n")

    if args.coherence:
        print("── COHERENCE: does the stored summary justify the stored stance? ──\n")
        bad, tally = run_coherence(conn, client, model, rows)
        rate = 100 * len(bad) / len(rows) if rows else 0
        print(f"\n  {len(bad)}/{len(rows)} stored verdicts contradict their own "
              f"summary ({rate:.0f}%)")
        for k, v in sorted(tally.items(), key=lambda kv: -kv[1]):
            print(f"    {k:24s} {v}")

    if args.rejudge:
        print("\n── REJUDGE: independent second opinion on the abstract ──\n")
        bad, tally = run_rejudge(conn, client, model, rows)
        rate = 100 * len(bad) / len(rows) if rows else 0
        print(f"\n  {len(bad)}/{len(rows)} stored verdicts flipped or came back "
              f"mixed ({rate:.0f}%)")
        for k, v in sorted(tally.items(), key=lambda kv: -kv[1]):
            print(f"    {k:24s} {v}")

    conn.close()


if __name__ == "__main__":
    main()
