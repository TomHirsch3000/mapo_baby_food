#!/usr/bin/env python3
"""
evaluate_claims.py — Judge each paper's stance on the claim it was collected for.

For every (claim, paper) link in claims.db, ask the local LLM whether the
abstract supports, refutes, or is neutral on the claim, and how strong the
evidence is. Results drive both the claim-node sizing and the support/refute
sections of the evidence view.

Resumable: rows that already have a stance are skipped unless --force.
Papers are processed best-first (keyword score, then citations) so a partial
run still yields the most useful evidence.

Usage:
    python backend/evaluate_claims.py --seed
    python backend/evaluate_claims.py --all --limit 500
    python backend/evaluate_claims.py back_to_sleep --force
"""

import argparse
import os
import sqlite3
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import console
import llm
from claims import CLAIMS, SUBJECTS, resolve_claim_keys

console.init()

DATA_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "claims.db")

STANCES = ("supports", "refutes", "neutral")
STRENGTHS = ("strong", "moderate", "limited", "mixed")

SYSTEM_PROMPT = (
    "You are a careful evidence analyst for paediatric research. "
    "You judge only what the abstract actually shows. "
    "Respond ONLY with valid JSON, no markdown, no commentary."
)

# The "finding" field comes FIRST on purpose. The model generates left to right,
# so writing out what the paper actually found before committing to a stance
# stops it from scoring topic-relevance as agreement - a 7B model will otherwise
# mark "Bed sharing is NOT a risk factor" as supporting "bed sharing increases
# risk", because every keyword matches.
STANCE_PROMPT = """\
CLAIM: "{claim}"

PAPER TITLE: {title}
ABSTRACT: {abstract}

Decide whether this paper's findings SUPPORT or REFUTE the CLAIM.

Respond with ONLY this JSON, filling the fields in order:
{{
  "finding": "<what the paper actually concluded, in your own words, max 20 words>",
  "direction": "<does that conclusion agree or disagree with the CLAIM? answer 'agrees', 'disagrees', or 'does not test it'>",
  "stance": "supports | refutes | neutral",
  "confidence": <0-100 integer>,
  "summary": "<one sentence, max 25 words, on what this paper found about the claim>",
  "evidence_strength": "strong | moderate | limited | mixed",
  "study_type": "<meta-analysis | rct | cohort | case-control | cross-sectional | review | case-report | other>"
}}

Rules:
- "agrees"        -> stance "supports"
- "disagrees"     -> stance "refutes"
- "does not test it" -> stance "neutral"
- Read negations carefully. Phrases like "no association", "was not a risk factor",
  "no significant difference", "did not reduce" mean the paper DISAGREES with a
  claim that asserts an effect. Matching keywords is NOT agreement.
- A paper that only describes the topic, or is inconclusive, is "neutral" with low confidence.
- Judge only from this abstract. Do not use outside knowledge.
- evidence_strength: strong = meta-analysis/large RCT; moderate = smaller RCT or prospective cohort; limited = cross-sectional, case-control, small or preliminary; mixed = conflicting findings.

Example of a REFUTING paper:
CLAIM: "Vitamin C prevents the common cold"
Abstract concludes: "Regular vitamin C supplementation had no effect on common cold incidence."
{{"finding": "Vitamin C supplementation did not reduce cold incidence", "direction": "disagrees", "stance": "refutes", "confidence": 90, "summary": "Found no effect of vitamin C on cold incidence.", "evidence_strength": "strong", "study_type": "meta-analysis"}}
"""


def ensure_schema(conn):
    """claim_papers gains its stance columns lazily so old DBs keep working."""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(claim_papers)").fetchall()}
    for name, decl in [
        ("stance", "TEXT"), ("confidence", "INTEGER"), ("stance_summary", "TEXT"),
        ("evidence_strength", "TEXT"), ("study_type", "TEXT"), ("evaluated_at", "TEXT"),
    ]:
        if name not in cols:
            conn.execute(f"ALTER TABLE claim_papers ADD COLUMN {name} {decl}")
    conn.commit()


def validate(data):
    """Clamp the model's output into the shapes the rest of the app expects."""
    if not isinstance(data, dict):
        return None

    stance = str(data.get("stance", "")).strip().lower()
    # Models like to pad ("clearly supports", "supports the claim") - match loosely.
    stance = next((s for s in STANCES if s in stance), None)

    # `direction` is written before `stance`, after the model has restated the
    # finding, so it is the more considered answer. When the two disagree the
    # model has usually pattern-matched keywords into `stance` - trust direction.
    direction = str(data.get("direction", "")).strip().lower()
    from_direction = None
    if "disagree" in direction:
        from_direction = "refutes"
    elif "agree" in direction:          # after "disagree", so this is a real agree
        from_direction = "supports"
    elif "not test" in direction or "does not" in direction:
        from_direction = "neutral"

    if from_direction:
        stance = from_direction
    if stance is None:
        return None

    try:
        confidence = max(0, min(100, int(float(data.get("confidence", 50)))))
    except (TypeError, ValueError):
        confidence = 50

    strength = str(data.get("evidence_strength", "")).strip().lower()
    strength = next((s for s in STRENGTHS if s in strength), "limited")

    summary = str(data.get("summary") or "").strip()

    return {
        "stance": stance,
        "confidence": confidence,
        "stance_summary": summary[:400],
        "evidence_strength": strength,
        "study_type": str(data.get("study_type") or "other").strip().lower()[:40],
    }


def evaluate_pair(client, model, claim_text, title, abstract):
    prompt = STANCE_PROMPT.format(
        claim=claim_text,
        title=(title or "")[:400],
        abstract=(abstract or "(no abstract)")[:1800],
    )
    raw = llm.call_llm(client, model, SYSTEM_PROMPT, prompt,
                       temperature=0.0, max_tokens=450)
    return validate(llm.parse_json_response(raw))


PENDING_SQL = """
    SELECT cp.claim_key, cp.paperId, p.title, p.abstract
    FROM claim_papers cp
    JOIN papers p USING(paperId)
    WHERE cp.claim_key IN ({placeholders})
      {stance_filter}
    ORDER BY cp.keyword_score DESC, p.cited_by_count DESC
    {limit_clause}
"""


def run(conn, client, model, claim_keys, limit=None, force=False):
    ensure_schema(conn)

    sql = PENDING_SQL.format(
        placeholders=",".join("?" * len(claim_keys)),
        stance_filter="" if force else "AND (cp.stance IS NULL OR cp.stance = '')",
        limit_clause=f"LIMIT {int(limit)}" if limit else "",
    )
    rows = conn.execute(sql, claim_keys).fetchall()

    if not rows:
        print("Nothing to evaluate - all pairs already have a stance "
              "(use --force to redo).")
        return 0

    print(f"Evaluating {len(rows)} (claim, paper) pairs with {model}...\n")
    done = failed = 0
    tally = {s: 0 for s in STANCES}
    started = time.time()

    for i, (claim_key, paper_id, title, abstract) in enumerate(rows, 1):
        claim_text = CLAIMS[claim_key]["claim"]
        try:
            result = evaluate_pair(client, model, claim_text, title, abstract)
        except Exception as e:
            print(f"  [{i}/{len(rows)}] {claim_key} {paper_id} - LLM error: {e}")
            failed += 1
            continue

        if not result:
            print(f"  [{i}/{len(rows)}] {claim_key} {paper_id} - unparseable response")
            failed += 1
            continue

        conn.execute("""
            UPDATE claim_papers
               SET stance = ?, confidence = ?, stance_summary = ?,
                   evidence_strength = ?, study_type = ?, evaluated_at = datetime('now')
             WHERE claim_key = ? AND paperId = ?
        """, (result["stance"], result["confidence"], result["stance_summary"],
              result["evidence_strength"], result["study_type"], claim_key, paper_id))
        done += 1
        tally[result["stance"]] += 1

        if done % 5 == 0:
            conn.commit()

        rate = (time.time() - started) / i
        eta = rate * (len(rows) - i)
        print(f"  [{i}/{len(rows)}] {result['stance']:8s} "
              f"({result['confidence']:3d}%) {result['evidence_strength']:8s} "
              f"{(title or '')[:56]:56s} ETA {eta/60:.0f}m")

    conn.commit()
    elapsed = (time.time() - started) / 60
    print(f"\nEvaluated {done}, failed {failed}, in {elapsed:.1f} min")
    print(f"  supports {tally['supports']}  refutes {tally['refutes']}  "
          f"neutral {tally['neutral']}")
    return done


def main():
    parser = argparse.ArgumentParser(description="LLM stance evaluation for claims")
    parser.add_argument("selection", nargs="*", help="claim / subject / domain keys")
    parser.add_argument("--seed", action="store_true", help="the proof set")
    parser.add_argument("--all", action="store_true", help="every claim")
    parser.add_argument("--limit", type=int, help="max pairs this run")
    parser.add_argument("--force", action="store_true", help="re-evaluate existing")
    parser.add_argument("--model", default=llm.DEFAULT_MODEL)
    parser.add_argument("--db", default=DB_PATH)
    args = parser.parse_args()

    if not args.selection and not args.seed and not args.all:
        print("[error] pass --seed, --all, or claim/subject/domain keys")
        raise SystemExit(1)

    if not llm.ping():
        print(f"[error] No Ollama server at {llm.OLLAMA_BASE}. Start it with: ollama serve")
        raise SystemExit(1)

    if not os.path.exists(args.db):
        print(f"[error] {args.db} not found - run import_claims.py first")
        raise SystemExit(1)

    keys = resolve_claim_keys(args.selection or None, seed=args.seed)
    client, model = llm.get_client(model=args.model)

    conn = sqlite3.connect(args.db)
    try:
        run(conn, client, model, keys, limit=args.limit, force=args.force)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
