#!/usr/bin/env python3
"""
compare_runs.py — Put every verdict for a gold row on ONE line, worst first.

A bake-off table says a model scored 65%. It does not say WHICH nine rows it
got wrong, or whether the labeller or the model was right about them. This
writes the flat file you actually adjudicate from: the hand label, the stored
mistral verdict, and every run in gold/runs/, side by side with the abstract
that decides it.

Rows are ordered by how much the verdicts disagree, so the top of the file is
the part worth a human's time. Ordering is the highlighting — a CSV has no
colour, and sorting costs nothing to read.

    python backend/compare_runs.py
    python backend/compare_runs.py --out /tmp/x.csv --top 20
"""

import argparse
import csv
import glob
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import console

console.init()

ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
GOLD = os.path.join(ROOT, "gold", "gold_set.csv")
RUNS = os.path.join(ROOT, "gold", "runs")
DEFAULT_OUT = os.path.join(ROOT, "gold", "comparison.csv")

NO_STANCE = {"does not test", "does not test it", "n/a", "na", "none", "-"}
RELEVANCE_ALIASES = {"not relevant": "background"}
TIERS = ("direct", "indirect", "framework", "background")
HARD = ("supports", "refutes", "mixed")      # a directional verdict
OFF_TOPIC = "does not test"


def gold_stance(row):
    v = (row.get("YOUR_stance") or "").strip().lower()
    if not v:
        return ""
    return OFF_TOPIC if v in NO_STANCE else v


def gold_relevance(row):
    v = (row.get("YOUR_relevance") or "").strip().lower()
    v = RELEVANCE_ALIASES.get(v, v)
    return v if v in TIERS else ""


def disagreement(truth, verdict):
    """How badly one verdict misses the hand label.

    A supports/refutes flip is not one unit worse than a near miss — it is the
    error that inverts a claim on the map, so it is scored as its own class.
    """
    if verdict is None:                      # declined to judge
        return 0 if truth == OFF_TOPIC else 1
    if truth == OFF_TOPIC:
        # `neutral` on an off-topic paper is the one-call prompt's only way of
        # declining, so it is a much smaller sin than a directional verdict.
        return 2 if verdict in HARD else 0.5
    if verdict == truth:
        return 0
    if {verdict, truth} == {"supports", "refutes"}:
        return 3
    return 1


def load_runs():
    runs = {}
    for path in sorted(glob.glob(os.path.join(RUNS, "*.json"))):
        name = os.path.basename(path)[:-5]
        try:
            runs[name] = json.load(open(path, encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"[warn] skipping {name}: {e}")
    return runs


def main():
    p = argparse.ArgumentParser(description="Flatten every verdict per gold row")
    p.add_argument("--out", default=DEFAULT_OUT)
    p.add_argument("--top", type=int, help="write only the N most contested rows")
    args = p.parse_args()

    rows = list(csv.DictReader(open(GOLD, encoding="utf-8")))
    runs = load_runs()
    if not runs:
        print(f"[warn] no runs in {RUNS} - only the stored mistral verdict will appear")

    # mistral's stored verdict is a run like any other; it just lives in the CSV.
    sources = [("mistral_1pass", None)] + [(n, n) for n in sorted(runs)]

    out = []
    for row in rows:
        truth = gold_stance(row)
        rec = {
            "n": row["n"],
            "stratum": row["stratum"],
            "labelled_by": row.get("labelled_by", ""),
            "gold_relevance": gold_relevance(row),
            "gold_stance": truth,
            "gold_notes": (row.get("YOUR_notes") or "").strip(),
            "claim_key": row["claim_key"],
            "tested_as": row["tested_as"],
            "title": row["title"],
            "citations": row["citations"],
        }

        score, flags, verdicts = 0.0, [], []
        for label, run_name in sources:
            if run_name is None:
                got = {"stance": row["model_stance"],
                       "confidence": row["model_confidence"],
                       "finding": row["model_finding"]}
            else:
                got = runs[run_name].get(row["n"]) or {}

            stance = got.get("stance") or None
            verdicts.append(stance)
            score += disagreement(truth, stance)

            rec[f"{label}__stance"] = stance if stance else (
                "UNPARSEABLE" if got.get("unparseable") else "(declined)")
            rec[f"{label}__conf"] = got.get("confidence", "")
            if "relevance" in got:
                rec[f"{label}__relevance"] = got.get("relevance", "")
                rec[f"{label}__why"] = got.get("relevance_reason", "")
            rec[f"{label}__finding"] = (got.get("finding") or "")[:300]

            if truth and truth != OFF_TOPIC and stance and \
                    {stance, truth} == {"supports", "refutes"}:
                flags.append(f"FLIP:{label}")
            if truth == OFF_TOPIC and stance in HARD:
                flags.append(f"OFFTOPIC-VERDICT:{label}")
            if got.get("unparseable"):
                flags.append(f"UNPARSEABLE:{label}")

        # Models contradicting each other is its own signal: it means the row is
        # hard, independently of whether the labeller happens to be right.
        real = [v for v in verdicts if v]
        if len(set(real)) > 1:
            score += len(set(real)) - 1
            flags.append("MODELS-SPLIT")
        if not truth:
            flags.append("UNLABELLED")

        rec["controversy"] = round(score, 1)
        rec["flags"] = " ".join(flags)
        rec["distinct_verdicts"] = len(set(real))
        rec["abstract"] = row["abstract"]      # last: it is what settles the row
        out.append(rec)

    # Most contested first; ties broken by citations, since a disputed verdict on
    # a heavily-cited paper moves the map further than one on an obscure paper.
    out.sort(key=lambda r: (-r["controversy"], -int(r["citations"] or 0)))
    for i, rec in enumerate(out, 1):
        rec["rank"] = i

    if args.top:
        out = out[:args.top]

    # Any column a human added to a previous export is theirs, and a re-run
    # must not eat it. Carry unknown columns forward, matched on `n` - the rank
    # changes between runs as new models are added, so it cannot be the key.
    carried = []
    if os.path.exists(args.out):
        with open(args.out, encoding="utf-8-sig", newline="") as f:
            prev = {r["n"]: r for r in csv.DictReader(f)}
        if prev:
            known = set(out[0]) | {"rank"}
            carried = [c for c in next(iter(prev.values())) if c not in known]
            for rec in out:
                for col in carried:
                    rec[col] = (prev.get(rec["n"], {}) or {}).get(col, "")
            if carried:
                kept = sum(1 for rec in out for c in carried if (rec.get(c) or "").strip())
                print(f"carried forward {carried} ({kept} non-empty cells)")

    lead = ["rank", "controversy", "flags", "distinct_verdicts", "n", "stratum",
            "labelled_by", "gold_relevance", "gold_stance", "gold_notes"]
    rest = [k for k in out[0] if k not in lead and k != "abstract"
            and k not in carried]
    fields = lead + rest + ["abstract"] + carried

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    # utf-8-sig: Excel on Windows reads a plain utf-8 CSV as cp1252 and turns
    # every curly quote in an abstract into mojibake. The BOM is what stops it.
    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)

    print(f"{args.out}  ({len(out)} rows, {len(fields)} columns)")
    print(f"sources: {', '.join(l for l, _ in sources)}\n")
    print(f"  {'rank':>4} {'ctrv':>5}  {'n':>3} {'gold':<14} " +
          " ".join(f"{l.replace('qwen3-8b-gpu__',''):<12}" for l, _ in sources) + " flags")
    for rec in out[:12]:
        cells = " ".join(f"{str(rec[f'{l}__stance'])[:12]:<12}" for l, _ in sources)
        print(f"  {rec['rank']:>4} {rec['controversy']:>5}  {rec['n']:>3} "
              f"{rec['gold_stance'] or '-':<14} {cells} {rec['flags'][:44]}")


if __name__ == "__main__":
    main()
