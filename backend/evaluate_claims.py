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
    python backend/evaluate_claims.py --all --stale     # resume a taxonomy re-run
    python backend/evaluate_claims.py back_to_sleep --force
"""

import argparse
import glob
import os
import sqlite3
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import console
import llm
from claims import CLAIMS, resolve_claim_keys, tested_text

console.init()

ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
DATA_DIR = os.path.join(ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "claims.db")

# Generous on purpose, and it must stay in step with bakeoff.py. A reasoning
# model spends tokens thinking BEFORE it writes any content, so a budget sized
# for a model that answers straight away truncates it mid-JSON and the row comes
# back unparseable. Measured: qwen3:8b failed 2 of 3 pairs at 450 and 0 of 57 at
# 1600 in the bake-off, which is the same prompt on the same model - the only
# difference was this number. A ceiling costs a terse model nothing.
MAX_TOKENS = 1600

# "mixed" is a first-class verdict, not a hedge. A meta-analysis can find that
# heavy screen use harms language WHILE educational programming helps it; forcing
# that into supports/refutes throws away the most interesting thing it says, and
# hands the reader a confident badge the abstract does not earn.
STANCES = ("supports", "refutes", "neutral", "mixed")
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
  "direction": "<does that conclusion agree or disagree with the CLAIM? answer 'agrees', 'disagrees', 'both', or 'does not test it'>",
  "stance": "supports | refutes | neutral | mixed",
  "confidence": <0-100 integer>,
  "summary": "<one sentence, max 25 words, on what this paper found about the claim>",
  "evidence_strength": "strong | moderate | limited | mixed",
  "study_type": "<meta-analysis | rct | cohort | case-control | cross-sectional | review | case-report | other>"
}}

Rules:
- "agrees"        -> stance "supports"
- "disagrees"     -> stance "refutes"
- "both"          -> stance "mixed"
- "does not test it" -> stance "neutral"
- Answer "both" when the abstract reports findings pointing BOTH ways on this
  claim - for example harm from a large or low-quality dose alongside benefit
  from a small or high-quality one. Do not average them into one direction, and
  do not pick the louder result. If you answer "both", the summary MUST state
  both sides.
- Read negations carefully. Phrases like "no association", "was not a risk factor",
  "no significant difference", "did not reduce" mean the paper DISAGREES with a
  claim that asserts an effect. Matching keywords is NOT agreement.
- A paper that only describes the topic, or is inconclusive, is "neutral" with low confidence.
- Judge only from this abstract. Do not use outside knowledge.
- evidence_strength: strong = meta-analysis/large RCT; moderate = smaller RCT or prospective cohort; limited = cross-sectional, case-control, small or preliminary; mixed = conflicting findings.

Example of a MIXED paper:
CLAIM: "Screen media should be avoided before 18-24 months"
Abstract concludes: "More screen time was associated with poorer language, but educational programming and co-viewing were associated with better language."
{{"finding": "Quantity of screen use harmed language; quality of screen use helped it", "direction": "both", "stance": "mixed", "confidence": 85, "summary": "More screen time tracked worse language, but educational and co-viewed content tracked better language.", "evidence_strength": "strong", "study_type": "meta-analysis"}}

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
        # The model is asked to restate the finding and pick a direction BEFORE
        # committing to a stance. Those two fields were being generated and then
        # thrown away, which left every verdict unauditable after the fact - the
        # only way to check one was to pay for inference again. Keep them.
        ("finding", "TEXT"), ("direction", "TEXT"),
        # Provenance. `claim_text_used` matters more than it looks: a claim's
        # wording changes between passes - twelve did on 2026-09-01, two of them
        # inverting outright - so knowing WHO answered is not enough to make two
        # passes comparable. Storing the sentence that was actually judged makes
        # every verdict self-describing, and a later comparison honest.
        ("evaluated_by", "TEXT"), ("prompt_version", "TEXT"),
        ("claim_text_used", "TEXT"),
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
    if "both" in direction:             # checked first: "agrees with both" is mixed
        from_direction = "mixed"
    elif "disagree" in direction:
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
        "finding": str(data.get("finding") or "").strip()[:400],
        "direction": direction[:60],
    }


def evaluate_pair(client, model, claim_text, title, abstract):
    prompt = STANCE_PROMPT.format(
        claim=claim_text,
        title=(title or "")[:400],
        abstract=(abstract or "(no abstract)")[:1800],
    )
    raw = llm.call_llm(client, model, SYSTEM_PROMPT, prompt,
                       temperature=0.0, max_tokens=MAX_TOKENS)
    return validate(llm.parse_json_response(raw))


PENDING_SQL = """
    SELECT cp.claim_key, cp.paperId, p.title, p.abstract
    FROM claim_papers cp
    JOIN papers p USING(paperId)
    WHERE cp.claim_key IN ({placeholders})
      -- A retracted paper is not evidence, whatever it concluded. Skipping it
      -- here also saves the five seconds of inference it would have cost.
      AND COALESCE(p.is_retracted, 0) = 0
      {stance_filter}
    ORDER BY cp.keyword_score DESC, p.cited_by_count DESC
    {limit_clause}
"""


def run(conn, client, model, claim_keys, limit=None, force=False, stale=False,
        prompt_version="current"):
    ensure_schema(conn)

    # `direction` is only ever written by the current evaluator, so a row that
    # has one has been judged under the present taxonomy and a row that has not
    # is either untouched or left over from an older one. That makes --stale the
    # resumable form of --force: kill it halfway, run it again, and it resumes
    # exactly where it stopped instead of starting the whole corpus over.
    if force:
        stance_filter = ""
    elif stale:
        stance_filter = "AND (cp.direction IS NULL OR cp.direction = '')"
    else:
        stance_filter = "AND (cp.stance IS NULL OR cp.stance = '')"

    sql = PENDING_SQL.format(
        placeholders=",".join("?" * len(claim_keys)),
        stance_filter=stance_filter,
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
        # The empirical wording, not the headline. A paper cannot test "should".
        claim_text = tested_text(claim_key)
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
                   evidence_strength = ?, study_type = ?, finding = ?, direction = ?,
                   evaluated_at = datetime('now'),
                   evaluated_by = ?, prompt_version = ?, claim_text_used = ?
             WHERE claim_key = ? AND paperId = ?
        """, (result["stance"], result["confidence"], result["stance_summary"],
              result["evidence_strength"], result["study_type"],
              result["finding"], result["direction"],
              model, prompt_version, claim_text, claim_key, paper_id))
        done += 1
        tally[result["stance"]] += 1

        # Commit per row, not per batch: batching held the write lock across
        # several LLM calls, which locked out any parallel shard.
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
          f"mixed {tally['mixed']}  neutral {tally['neutral']}")
    return done


def report_coverage(conn):
    """Which model judged what, and whether it judged the current wording.

    The two shards are deliberately run on different models — the Mac holds a
    20B and this laptop cannot — so a claim's netSupport carries a model effect
    when compared against another claim's. That is a trade taken knowingly, for
    the accuracy, and it is only safe while it stays visible. This is what keeps
    it visible.
    """
    cols = {r[1] for r in conn.execute("PRAGMA table_info(claim_papers)")}
    if "evaluated_by" not in cols:
        print("[error] no provenance columns — this DB predates the split")
        return

    rows = conn.execute("""
        SELECT COALESCE(NULLIF(evaluated_by, ''), '(unevaluated)') AS who,
               COUNT(*), COUNT(DISTINCT claim_key)
          FROM claim_papers GROUP BY who ORDER BY 2 DESC""").fetchall()
    print(f"{sum(r[1] for r in rows):,} pairs")
    print()
    print(f"  {'evaluated_by':<22} {'pairs':>7} {'claims':>7}")
    print("  " + "-" * 38)
    for who, pairs, claims in rows:
        print(f"  {who:<22} {pairs:>7,} {claims:>7}")

    # Progress against the shards, and the one failure they exist to prevent:
    # a claim touched by BOTH machines. A claim part-done shows the old model
    # alongside the new one, which is normal mid-pass and not what we are
    # looking for - so the test is against the model each shard is meant to use,
    # not against "more than one model appears".
    shards = {}
    for path in sorted(glob.glob(os.path.join(ROOT, "shards", "*.txt"))):
        lines = open(path, encoding="utf-8").read().rstrip("\n").split("\n")
        model = next((l.split(":", 1)[1].strip() for l in lines
                      if l.startswith("# model:")), None)
        if model:
            shards[os.path.basename(path)[:-4]] = (model, lines[-1].split())

    for name, (want, keys) in shards.items():
        ph = ",".join("?" * len(keys))
        total = conn.execute(
            f"SELECT COUNT(*) FROM claim_papers WHERE claim_key IN ({ph})",
            keys).fetchone()[0]
        done = conn.execute(
            f"SELECT COUNT(*) FROM claim_papers WHERE evaluated_by = ? "
            f"AND claim_key IN ({ph})", [want] + keys).fetchone()[0]
        # Anything in this shard carrying a model that is neither the shard's
        # own nor the historical baseline means the other machine ran it too.
        intruders = conn.execute(
            f"SELECT DISTINCT evaluated_by FROM claim_papers "
            f"WHERE claim_key IN ({ph}) AND evaluated_by NOT IN (?, 'mistral') "
            f"AND evaluated_by IS NOT NULL AND evaluated_by != ''",
            keys + [want]).fetchall()
        pct = 100 * done / total if total else 0
        print()
        print(f"  shard {name:<10} {want:<16} {done:>5,}/{total:<5,} {pct:5.1f}%")
        if intruders:
            print(f"    ** ALSO judged by {[i[0] for i in intruders]} — the shards "
                  f"overlapped, re-run one half **")

    # A verdict reached against wording the registry no longer holds is stale,
    # whoever produced it. Twelve claims were reworded on 2026-09-01 and two
    # inverted outright, so this is not hypothetical.
    stale = []
    for key in CLAIMS:
        n = conn.execute(
            "SELECT COUNT(*) FROM claim_papers WHERE claim_key = ? "
            "AND claim_text_used IS NOT NULL AND claim_text_used != '' "
            "AND claim_text_used != ?", (key, tested_text(key))).fetchone()[0]
        if n:
            stale.append((key, n))
    print()
    print(f"  verdicts judged against superseded wording: {sum(n for _, n in stale):,}")
    for key, n in stale:
        print(f"    {key:<28} {n}")
    if stale:
        print("    -> those claims were reworded after judging; re-run them")


def main():
    parser = argparse.ArgumentParser(description="LLM stance evaluation for claims")
    parser.add_argument("selection", nargs="*", help="claim / topic keys")
    parser.add_argument("--seed", action="store_true", help="the proof set")
    parser.add_argument("--all", action="store_true", help="every claim")
    parser.add_argument("--limit", type=int, help="max pairs this run")
    parser.add_argument("--force", action="store_true",
                        help="re-evaluate everything, including rows already redone")
    parser.add_argument("--stale", action="store_true",
                        help="re-evaluate only rows judged before the reasoning "
                             "fields existed - the resumable form of --force")
    parser.add_argument("--model", default=llm.DEFAULT_MODEL)
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--coverage", action="store_true",
                        help="report which model judged what, and run nothing")
    args = parser.parse_args()

    if args.coverage:
        conn = sqlite3.connect(args.db, timeout=60)
        try:
            report_coverage(conn)
        finally:
            conn.close()
        return

    if not args.selection and not args.seed and not args.all:
        print("[error] pass --seed, --all, or claim/topic keys")
        raise SystemExit(1)

    if not llm.ping():
        print(f"[error] No Ollama server at {llm.OLLAMA_BASE}. Start it with: ollama serve")
        raise SystemExit(1)

    if not os.path.exists(args.db):
        print(f"[error] {args.db} not found - run import_claims.py first")
        raise SystemExit(1)

    keys = resolve_claim_keys(args.selection or None, seed=args.seed)
    client, model = llm.get_client(model=args.model)

    conn = sqlite3.connect(args.db, timeout=60)
    # Shards of disjoint claims can be evaluated by several processes at once.
    # WAL lets them interleave; the busy timeout absorbs the brief overlap when
    # two of them commit at the same moment.
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=60000")
    try:
        run(conn, client, model, keys, limit=args.limit, force=args.force,
            stale=args.stale)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
