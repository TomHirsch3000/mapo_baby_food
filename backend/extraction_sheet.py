#!/usr/bin/env python3
"""
extraction_sheet.py — Flatten extracted paper records into a sheet to validate.

The point of extracting before judging is that validation decomposes. Checking
"does this abstract support this claim" means reading the abstract and holding a
claim in your head at the same time. Checking "did this paper measure prone
sleeping, in infants under one, and did the risk go up" is four small factual
questions, each answerable by ctrl-F.

So this writes one row per FINDING, not per paper, with the paper-level fields
repeated across its findings and the abstract on every row. A row is checkable
without leaving it.

Two columns are deliberately verbatim - `age_quote` and `effect_size`. They are
the anchors: if a quote is not in the abstract, the extraction invented it, and
that is visible without judgement. The same trick the original evaluator used for
its `quote` field, applied to the numbers instead.

Anything a human adds is carried forward on a re-run, keyed on paperId+finding
index, the way compare_runs.py and build_audit_table.py already do.

    python backend/extraction_sheet.py --in <extract_gold.json>
"""

import argparse
import csv
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import console

console.init()

ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
GOLD = os.path.join(ROOT, "gold", "gold_set.csv")
DEFAULT_OUT = os.path.join(ROOT, "gold", "extraction_sheet.csv")

WORD = re.compile(r"[a-z0-9]+")


def words(text):
    """Alphanumeric word stream — punctuation and spacing discarded.

    A verbatim check has to survive the abstract using a curly apostrophe or a
    different dash. Comparing word streams means a quote only fails on a real
    difference, not on typography.
    """
    return " ".join(WORD.findall((text or "").lower()))


def verbatim(fragment, abstract):
    """'ok' if the fragment is really in the abstract, 'MISSING' if not, '' if
    nothing was claimed."""
    if not (fragment or "").strip():
        return ""
    return "ok" if words(fragment) in words(abstract) else "MISSING"


def main():
    p = argparse.ArgumentParser(description="One row per finding, for validation")
    p.add_argument("--in", dest="src", required=True)
    p.add_argument("--out", dest="out", default=DEFAULT_OUT)
    args = p.parse_args()

    papers = {r["paperId"]: r for r in json.load(open(args.src, encoding="utf-8"))}
    meta = {}
    for r in csv.DictReader(open(GOLD, encoding="utf-8")):
        meta.setdefault(r["paperId"], r)

    rows = []
    for pid, rec in papers.items():
        m = meta.get(pid, {})
        abstract = m.get("abstract", "")
        base = {
            "paperId": pid,
            "title": m.get("title", ""),
            "citations": m.get("citations", ""),
            "study_type": rec.get("study_type", ""),
            "sample_size": rec.get("sample_size", ""),
            "population": rec.get("population", ""),
            "age_min_months": rec.get("age_min_months"),
            "age_max_months": rec.get("age_max_months"),
            "age_basis": rec.get("age_basis", ""),
            "age_quote": rec.get("age_quote", ""),
            "age_quote_check": verbatim(rec.get("age_quote"), abstract),
            "funding": rec.get("funding", ""),
            "assumptions": " | ".join(rec.get("assumptions") or []),
            "n_findings": len(rec.get("findings") or []),
            "extractor_notes": rec.get("notes", ""),
        }
        findings = rec.get("findings") or [{}]
        for i, f in enumerate(findings):
            rows.append(dict(base,
                finding_no=i + 1,
                exposure=f.get("exposure", ""),
                comparator=f.get("comparator", ""),
                outcome=f.get("outcome", ""),
                outcome_desirable=f.get("outcome_desirable", ""),
                effect=f.get("effect", ""),
                effect_size=f.get("effect_size", ""),
                effect_size_check=verbatim(f.get("effect_size"), abstract),
                finding=f.get("finding", ""),
                YOUR_VERDICT="",      # ok | wrong | partial
                YOUR_NOTES="",
                abstract=abstract))

    # Papers with nothing extracted, and rows whose verbatim anchors failed,
    # sort to the top: they need a person more than a correct row does.
    rows.sort(key=lambda r: (r["n_findings"] != 0,
                             r["effect_size_check"] != "MISSING",
                             r["age_quote_check"] != "MISSING",
                             r["paperId"], r["finding_no"]))

    carried = []
    if os.path.exists(args.out):
        with open(args.out, encoding="utf-8-sig", newline="") as f:
            prev = {(r["paperId"], r["finding_no"]): r for r in csv.DictReader(f)}
        if prev:
            known = set(rows[0])
            carried = [c for c in next(iter(prev.values())) if c not in known]
            for r in rows:
                for col in carried:
                    r[col] = prev.get((r["paperId"], str(r["finding_no"])), {}).get(col, "")
            if carried:
                print(f"carried forward {carried}")

    lead = ["paperId", "finding_no", "YOUR_VERDICT", "YOUR_NOTES", "title",
            "study_type", "sample_size", "population"]
    rest = [k for k in rows[0] if k not in lead and k != "abstract" and k not in carried]
    fields = lead + rest + carried + ["abstract"]

    with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    n_papers = len(papers)
    empty = sum(1 for r in json.load(open(args.src, encoding="utf-8"))
                if not (r.get("findings") or []))
    print(f"{args.out}\n")
    print(f"  {n_papers} papers -> {len(rows)} rows (one per finding)")
    print(f"  papers with no findings extracted : {empty}")
    print(f"  effect_size not found in abstract : "
          f"{sum(1 for r in rows if r['effect_size_check'] == 'MISSING')}")
    print(f"  age_quote not found in abstract   : "
          f"{sum(1 for r in rows if r['age_quote_check'] == 'MISSING')}")
    print("\n  Fill YOUR_VERDICT with: ok | wrong | partial")
    print("  Rows whose verbatim anchors failed are sorted to the top.")


if __name__ == "__main__":
    main()
