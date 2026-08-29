#!/usr/bin/env python3
"""
bakeoff.py — Run the gold set through a model and score it against hand labels.

The point of this file is that a full evaluation pass is 14-25 hours, so a
prompt or a model can only be changed a handful of times before the project
stops moving. `gold/gold_set.csv` is 60 hand-labelled pairs; running those 60
takes minutes, which turns "is this better?" from an overnight run and an
impression into a number.

Two failure modes are scored SEPARATELY, because an overall accuracy hides the
one that matters:

  relevance   does the paper bear on the claim at all? The current corpus scores
              bed-sharing papers against a pacifier claim and a circumcision
              hypothesis against a sleep-position claim.
  stance      which way does it point? On the 15 `complement` rows - where the
              paper reports the OPPOSITE exposure ("prone increases risk" rather
              than "supine reduces risk") - mistral currently scores at chance.
              An 80% overall that is 50% on those 15 is the number that produced
              the map as it stands.

Resumable and idempotent, like every other stage: each row's result is written
to gold/runs/<model>__<prompt>.json as it completes, and a re-run skips what is
already there. Kill it halfway and start it again.

Usage:
    python backend/bakeoff.py --model gpt-oss:20b            # run, then score
    python backend/bakeoff.py --model gpt-oss:20b --compare  # no labels needed
    python backend/bakeoff.py --score-only                   # score every run held
    python backend/bakeoff.py --model mistral --limit 10     # a quick smoke test
"""

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import console
import llm
from evaluate_claims import STANCE_PROMPT, SYSTEM_PROMPT, validate

console.init()

ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
GOLD_CSV = os.path.join(ROOT, "gold", "gold_set.csv")
RUNS_DIR = os.path.join(ROOT, "gold", "runs")

STRATA = ("complement", "refutes", "supports", "neutral", "mixed")

# A labeller working in Numbers or Excel is editing a DIFFERENT file to the one
# this reads, and the failure is silent: the CSV still parses, every YOUR_stance
# is still blank, and the scorer reports "no hand labels yet" over a spreadsheet
# full of them. So the sync is done here rather than left as a step to remember.
NUMBERS_DOC = os.path.join(ROOT, "gold", "gold_set.numbers")

# What a labeller writes when the paper does not test the claim at all. The
# schema wants the stance left blank on `framework` and `background`, but a blank
# is ambiguous - it reads the same as "not labelled yet" - so an explicit marker
# is the better habit, and is accepted rather than corrected.
NO_STANCE = {"does not test", "does not test it", "n/a", "na", "none", "-"}

# Generous, because a reasoning model spends tokens thinking BEFORE it writes any
# content. gpt-oss:20b at 600 returns an empty string on ~11% of pairs - not
# truncated JSON, nothing at all - and an empty response scored as a failure would
# have been read as "this model cannot hold the output format" when the real cause
# was a budget set for a model that does not think out loud. max_tokens is a
# ceiling rather than a target, so raising it costs a non-reasoning model nothing.
MAX_TOKENS = 1600


# ─────────────────────────────────────────────────────────────────────────────
# Prompts under test
# ─────────────────────────────────────────────────────────────────────────────
#
# "current" is imported from evaluate_claims rather than copied, so the baseline
# is genuinely the same code path that produced the database - not a
# reconstruction of it that has quietly drifted.
def build_current(row):
    return STANCE_PROMPT.format(
        claim=row["tested_as"],
        title=(row["title"] or "")[:400],
        abstract=(row["abstract"] or "(no abstract)")[:1800],
    )


PROMPTS = {
    "current": (SYSTEM_PROMPT, build_current, validate),
}

# `decomposed` is registered here once prompts_v2 grows it. Keeping the registry
# explicit means adding a candidate prompt is one entry, not an edit to the loop.
try:
    import prompts_v2
    if hasattr(prompts_v2, "DECOMPOSED_PROMPT"):
        PROMPTS["decomposed"] = (
            prompts_v2.STANCE_SYSTEM,
            lambda row: prompts_v2.DECOMPOSED_PROMPT.format(
                tested=row["tested_as"],
                title=(row["title"] or "")[:400],
                abstract=(row["abstract"] or "(no abstract)")[:1800],
            ),
            prompts_v2.validate_decomposed,
        )
except (ImportError, AttributeError):
    pass


def sync_from_numbers():
    """If the .numbers doc is newer than the CSV, export over the CSV first.

    Opening a CSV in Numbers and saving produces a SEPARATE .numbers file and
    leaves the CSV untouched, so without this the labels are invisible to the
    scorer. The export is one-way (.numbers -> .csv) and runs only when the
    spreadsheet is the newer of the two, so it cannot clobber newer CSV edits.
    """
    if not os.path.exists(NUMBERS_DOC):
        return
    if (os.path.exists(GOLD_CSV)
            and os.path.getmtime(GOLD_CSV) >= os.path.getmtime(NUMBERS_DOC)):
        return

    out = os.path.join(tempfile.mkdtemp(), "export")
    script = (
        'tell application "Numbers"\n'
        '  set d to open POSIX file "%s"\n'
        '  export d to POSIX file "%s" as CSV\n'
        'end tell' % (NUMBERS_DOC, out)
    )
    try:
        subprocess.run(["osascript", "-e", script], check=True,
                       capture_output=True, timeout=120)
        src = out if os.path.isfile(out) else next(
            (os.path.join(out, f) for f in sorted(os.listdir(out))), None)
        if not src:
            raise RuntimeError("Numbers produced no CSV")
        shutil.copyfile(src, GOLD_CSV)
        print("[sync] labels pulled from gold_set.numbers -> gold_set.csv")
    except Exception as e:
        print("[warn] could not read gold_set.numbers (%s)." % e)
        print("       Export it over gold_set.csv by hand: File > Export To > CSV")


def load_gold():
    sync_from_numbers()
    if not os.path.exists(GOLD_CSV):
        raise SystemExit(f"[error] {GOLD_CSV} not found")
    with open(GOLD_CSV, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run_path(model, prompt_name):
    safe = model.replace(":", "-").replace("/", "-")
    return os.path.join(RUNS_DIR, f"{safe}__{prompt_name}.json")


def load_run(model, prompt_name):
    path = run_path(model, prompt_name)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_run(model, prompt_name, results):
    os.makedirs(RUNS_DIR, exist_ok=True)
    with open(run_path(model, prompt_name), "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1, sort_keys=True)


def run(model, prompt_name, limit=None, force=False):
    system, build, check = PROMPTS[prompt_name]
    rows = load_gold()
    results = {} if force else load_run(model, prompt_name)

    todo = [r for r in rows if r["n"] not in results]
    if limit:
        todo = todo[:limit]
    if not todo:
        print(f"[{model} / {prompt_name}] all {len(results)} rows already run.")
        return results

    print(f"[{model} / {prompt_name}] {len(todo)} to run "
          f"({len(results)} cached)\n")
    started = time.time()
    for i, row in enumerate(todo, 1):
        t = time.time()
        try:
            raw = llm.call_llm(llm.get_client(model=model)[0], model, system,
                               build(row), temperature=0.0, max_tokens=MAX_TOKENS)
            parsed = check(llm.parse_json_response(raw))
        except Exception as e:
            print(f"  [{i}/{len(todo)}] #{row['n']:>2s} ERROR {e}")
            continue
        elapsed = time.time() - t

        if not parsed:
            # An unparseable response is a real result, not a gap to retry away:
            # a model that cannot hold the output format is worse at the job, and
            # hiding that behind a retry flatters it in the scoring.
            results[row["n"]] = {"stance": None, "unparseable": True,
                                 "seconds": round(elapsed, 1)}
            print(f"  [{i}/{len(todo)}] #{row['n']:>2s} {elapsed:5.1f}s  UNPARSEABLE")
        else:
            parsed["seconds"] = round(elapsed, 1)
            results[row["n"]] = parsed
            print(f"  [{i}/{len(todo)}] #{row['n']:>2s} {elapsed:5.1f}s  "
                  f"{parsed['stance']:8s}  {row['title'][:52]}")

        save_run(model, prompt_name, results)   # per row: kill it any time

    mean = (time.time() - started) / max(1, len(todo))
    print(f"\n  mean {mean:.1f}s/pair -> a 7,769-pair pass would take "
          f"{mean * 7769 / 3600:.1f} h ({mean * 13100 / 3600:.1f} h two-call)")
    return results


def score(results, rows):
    """Agreement with the hand labels, overall and per stratum."""
    # "does not test" is a RELEVANCE judgement, not a stance. Counting it as a
    # stance the model got wrong would penalise a model for the one thing the
    # labeller and the model actually agree on.
    def truth_of(r):
        v = (r.get("YOUR_stance") or "").strip().lower()
        return None if (not v or v in NO_STANCE) else v

    labelled = [r for r in rows if truth_of(r)]
    if not labelled:
        return None

    tally = {s: [0, 0] for s in STRATA}       # [correct, total]
    overall = [0, 0]
    unparseable = 0
    for row in labelled:
        got = results.get(row["n"])
        if not got:
            continue
        if got.get("unparseable"):
            unparseable += 1
        truth = truth_of(row)
        ok = (got.get("stance") == truth)
        st = row["stratum"]
        tally[st][1] += 1
        tally[st][0] += int(ok)
        overall[1] += 1
        overall[0] += int(ok)

    return {"overall": overall, "strata": tally, "unparseable": unparseable,
            "labelled": len(labelled)}


def print_scores(all_scores):
    if not all_scores:
        print("\nNo hand labels yet - fill YOUR_stance in gold/gold_set.csv.")
        return

    name_w = max(len(n) for n in all_scores)
    head = f"  {'run':{name_w}}   overall  " + "  ".join(f"{s[:10]:>10}" for s in STRATA)
    print("\n" + head)
    print("  " + "-" * (len(head) - 2))
    for name, s in all_scores.items():
        c, t = s["overall"]
        cells = []
        for st in STRATA:
            cc, tt = s["strata"][st]
            cells.append(f"{(100*cc/tt):>9.0f}%" if tt else f"{'-':>10}")
        pct = f"{100*c/t:.0f}%" if t else "-"
        print(f"  {name:{name_w}}   {pct:>6} {c:>2}/{t:<2} " + " ".join(cells))

    print("\n  `complement` is the column that decides this. It is the 15 rows where")
    print("  the paper reports the OPPOSITE exposure to the claim. An overall score")
    print("  that looks fine while that column sits near 50% is the current map.")


def main():
    p = argparse.ArgumentParser(description="Score a model+prompt on the gold set")
    p.add_argument("--model", help="ollama model tag, e.g. gpt-oss:20b")
    p.add_argument("--prompt", default="current", choices=sorted(PROMPTS),
                   help="which candidate prompt to run")
    p.add_argument("--limit", type=int, help="run only the first N unrun rows")
    p.add_argument("--force", action="store_true", help="discard the cached run")
    p.add_argument("--compare", action="store_true",
                   help="print model vs stored verdict side by side; no labels needed")
    p.add_argument("--score-only", action="store_true",
                   help="score every run already on disk, run nothing")
    args = p.parse_args()

    rows = load_gold()

    if not args.score_only:
        if not args.model:
            raise SystemExit("[error] pass --model (or --score-only)")
        if not llm.ping():
            raise SystemExit(f"[error] no ollama at {llm.OLLAMA_BASE} - `ollama serve`")
        results = run(args.model, args.prompt, limit=args.limit, force=args.force)

        if args.compare:
            print(f"\n  {'#':>3} {'stratum':11} {'stored':9} {'new':9}  title")
            by_n = {r["n"]: r for r in rows}
            for n in sorted(results, key=int):
                row, got = by_n[n], results[n]
                flag = "  <- differs" if got.get("stance") != row["model_stance"] else ""
                print(f"  {n:>3} {row['stratum']:11} {row['model_stance']:9} "
                      f"{str(got.get('stance')):9}  {row['title'][:44]}{flag}")

    # Score whatever is on disk, so adding a cell never means re-running the others.
    all_scores = {}
    if os.path.isdir(RUNS_DIR):
        for fn in sorted(os.listdir(RUNS_DIR)):
            if not fn.endswith(".json"):
                continue
            name = fn[:-5].replace("__", " / ")
            s = score(load_run(*fn[:-5].split("__")), rows)
            if s:
                all_scores[name] = s

    # The baseline needs no run: the stored verdicts ARE mistral on the current
    # prompt, so it is scored straight out of the CSV.
    base = score({r["n"]: {"stance": r["model_stance"]} for r in rows}, rows)
    if base:
        all_scores["mistral / current (stored)"] = base

    print_scores(all_scores)


if __name__ == "__main__":
    main()
