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
import polarity
import prompts_v2
from claims import CLAIMS
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


# A candidate is a runner: (client, model, row) -> (result | None, calls made).
# Returning the call count rather than assuming it is what lets the per-pass
# projection stay honest for a design where most pairs stop after one call.
def _one_call(system, build, check):
    """Wrap a single-call prompt in the runner signature the loop expects."""
    def runner(client, model, row):
        raw = llm.call_llm(client, model, system, build(row),
                           temperature=0.0, max_tokens=MAX_TOKENS)
        return check(llm.parse_json_response(raw)), 1
    return runner


def claim_population(claim_key):
    """What the CLAIM is about, fed to the screen so the model is not left
    inferring the intended population from the paper it is judging — which is
    circular, and is how a study of eight-year-olds gets called `direct`."""
    return (CLAIMS.get(claim_key) or {}).get("age_range") or "infants and toddlers"


def _decomposed(client, model, row):
    """SCREEN, then STANCE only for papers the screen says bear on the claim.

    The screened-out papers are the point. They never reach a question about
    direction, so nothing they might have said can leak into a verdict — and
    they cost one cheap call instead of two.
    """
    title = (row["title"] or "")[:400]
    abstract = (row["abstract"] or "(no abstract)")[:1800]

    raw = llm.call_llm(
        client, model, prompts_v2.SCREEN_SYSTEM,
        prompts_v2.SCREEN_PROMPT.format(
            tested=row["tested_as"],
            population=claim_population(row["claim_key"]),
            title=title, abstract=abstract),
        temperature=0.0, max_tokens=MAX_TOKENS)
    screen = prompts_v2.validate_screen(llm.parse_json_response(raw))
    if screen is None:
        return None, 1

    if screen["relevance"] not in prompts_v2.SCORED_TIERS:
        # Screened out, and that IS the answer. `stance: None` is a refusal to
        # judge, not a missing value, and the scorer counts it as the win it is.
        return dict(screen, stance=None, screened_out=True), 1

    raw = llm.call_llm(
        client, model, prompts_v2.STANCE_SYSTEM,
        prompts_v2.STANCE_PROMPT.format(
            tested=row["tested_as"], title=title, abstract=abstract,
            relevance_line=prompts_v2.RELEVANCE_LINE[screen["relevance"]],
            exposure=screen["exposure"] or "(not stated)",
            outcome=screen["outcome"] or "(not stated)",
            population=screen["population"] or "(not stated)"),
        temperature=0.0, max_tokens=MAX_TOKENS)
    stance = prompts_v2.validate_stance(llm.parse_json_response(raw))
    if stance is None:
        return None, 2
    return dict(screen, **stance, screened_out=False), 2


def _polarity_v2(client, model, row):
    """BACKLOG 1c, second attempt. See the V2 note in polarity.py for why."""
    cfg = CLAIMS.get(row["claim_key"]) or {}
    sign = cfg.get("claim_sign")
    if sign is None:
        return None, 0

    raw = llm.call_llm(
        client, model, polarity.SYSTEM,
        polarity.PROMPT_V2.format(
            claim_exposure=cfg.get("claim_exposure") or "(not recorded)",
            claim_outcome=cfg.get("claim_outcome") or "(not recorded)",
            title=(row["title"] or "")[:400],
            abstract=(row["abstract"] or "(no abstract)")[:1800]),
        temperature=0.0, max_tokens=MAX_TOKENS)

    reported = polarity.validate_v2(llm.parse_json_response(raw))
    stance, reason = polarity.resolve(sign, reported)
    if stance is None:
        return None, 1
    return dict(reported, stance=stance, resolved_by=reason), 1


def _polarity(client, model, row):
    """BACKLOG 1c. The model reports facts; Python computes the verdict.

    Needs `claim_sign`, `claim_exposure` and `claim_outcome` on the registry
    (1d). A claim without them is skipped rather than guessed at, so a
    half-filled registry shows up as missing rows instead of as bad scores.
    """
    cfg = CLAIMS.get(row["claim_key"]) or {}
    sign = cfg.get("claim_sign")
    if sign is None:
        return None, 0                    # registry not filled in for this claim

    raw = llm.call_llm(
        client, model, polarity.SYSTEM,
        polarity.PROMPT.format(
            claim_exposure=cfg.get("claim_exposure") or "(not recorded)",
            claim_outcome=cfg.get("claim_outcome") or "(not recorded)",
            title=(row["title"] or "")[:400],
            abstract=(row["abstract"] or "(no abstract)")[:1800]),
        temperature=0.0, max_tokens=MAX_TOKENS)

    reported = polarity.validate(llm.parse_json_response(raw))
    stance, reason = polarity.resolve(sign, reported)
    if stance is None:
        return None, 1
    # `resolved_by` carries the arithmetic that produced the verdict, so a wrong
    # row can be traced to the field that caused it rather than re-run blind.
    return dict(reported, stance=stance, resolved_by=reason), 1


PROMPTS = {
    "current": _one_call(SYSTEM_PROMPT, build_current, validate),
    "decomposed": _decomposed,
    "polarity": _polarity,
    "polarity2": _polarity_v2,
}


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
    runner = PROMPTS[prompt_name]
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
    client = llm.get_client(model=model)[0]
    started = time.time()
    for i, row in enumerate(todo, 1):
        t = time.time()
        try:
            parsed, calls = runner(client, model, row)
        except Exception as e:
            print(f"  [{i}/{len(todo)}] #{row['n']:>2s} ERROR {e}")
            continue
        elapsed = time.time() - t

        if not parsed:
            # An unparseable response is a real result, not a gap to retry away:
            # a model that cannot hold the output format is worse at the job, and
            # hiding that behind a retry flatters it in the scoring.
            results[row["n"]] = {"stance": None, "unparseable": True,
                                 "seconds": round(elapsed, 1), "calls": calls}
            print(f"  [{i}/{len(todo)}] #{row['n']:>2s} {elapsed:5.1f}s  UNPARSEABLE")
        else:
            parsed["seconds"] = round(elapsed, 1)
            parsed["calls"] = calls
            results[row["n"]] = parsed
            # A screened-out paper has no stance, and printing the tier instead
            # is the more useful line: it says WHY there is no verdict.
            verdict = parsed.get("stance") or f"[{parsed.get('relevance', '?')}]"
            print(f"  [{i}/{len(todo)}] #{row['n']:>2s} {elapsed:5.1f}s  "
                  f"{verdict:12s}  {row['title'][:48]}")

        save_run(model, prompt_name, results)   # per row: kill it any time

    mean = (time.time() - started) / max(1, len(todo))
    per_pair = sum(r.get("calls", 1) for r in results.values()) / max(1, len(results))
    print(f"\n  mean {mean:.1f}s/pair, {per_pair:.2f} calls/pair "
          f"-> a 7,769-pair pass would take {mean * 7769 / 3600:.1f} h")
    return results


# "does not test" is a RELEVANCE judgement, not a stance. Counting it as a
# stance the model got wrong would penalise a model for the one thing the
# labeller and the model actually agree on.
def truth_of(row):
    v = (row.get("YOUR_stance") or "").strip().lower()
    return None if (not v or v in NO_STANCE) else v


# Labels written before the four-tier rubric settled. "not relevant" is
# unambiguously `background`; "does not test" names the stance rather than the
# tier, so it cannot be resolved and that row sits out the relevance scoring
# rather than being guessed at.
RELEVANCE_ALIASES = {"not relevant": "background"}


def relevance_of(row):
    v = (row.get("YOUR_relevance") or "").strip().lower()
    v = RELEVANCE_ALIASES.get(v, v)
    return v if v in prompts_v2.RELEVANCE_TIERS else None


def score(results, rows):
    """Agreement with the hand labels: stance, and whether the paper bears on
    the claim at all.

    The second half exists because the first half cannot see the largest error.
    A stance table necessarily drops every row the gold set marks "does not
    test" — 34 of these 60 — which is precisely where a one-call prompt fails,
    since it has no way to answer "this paper is not about that" and must
    return a stance regardless.
    """
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

    # A verdict asserted about a paper that does not bear on the claim. Lower is
    # better, and a one-call prompt scores 100% here by construction — that is
    # the finding, not a bug in the scoring.
    false_stance = [0, 0]
    for row in rows:
        if truth_of(row) or relevance_of(row) not in ("framework", "background"):
            continue
        got = results.get(row["n"])
        if not got or got.get("unparseable"):
            continue
        false_stance[1] += 1
        false_stance[0] += int(bool(got.get("stance")))

    # Only a prompt that reports a tier can be scored on one. `bears` is the
    # coarser and more important of the two: the four-way tier is a judgement
    # call at the margins, but direct/indirect versus framework/background is
    # the decision that gates whether the expensive call happens at all.
    tier, bears = [0, 0], [0, 0]
    for row in rows:
        truth_rel = relevance_of(row)
        got = results.get(row["n"])
        if not truth_rel or not got or not got.get("relevance"):
            continue
        tier[1] += 1
        tier[0] += int(got["relevance"] == truth_rel)
        bears[1] += 1
        bears[0] += int((got["relevance"] in prompts_v2.SCORED_TIERS)
                        == (truth_rel in prompts_v2.SCORED_TIERS))

    calls = [r.get("calls", 1) for r in results.values() if isinstance(r, dict)]
    return {"overall": overall, "strata": tally, "unparseable": unparseable,
            "labelled": len(labelled), "false_stance": false_stance,
            "tier": tier, "bears": bears,
            "calls": sum(calls) / len(calls) if calls else 1.0}


def print_scores(all_scores):
    if not all_scores:
        print("\nNo hand labels yet - fill YOUR_stance in gold/gold_set.csv.")
        return

    def pct(pair, width=9):
        c, t = pair
        return f"{(100 * c / t):>{width}.0f}%" if t else f"{'-':>{width + 1}}"

    name_w = max(len(n) for n in all_scores)

    head = f"  {'run':{name_w}}   overall  " + "  ".join(f"{s[:10]:>10}" for s in STRATA)
    print("\n  STANCE — which way does it point?  (scored on the rows that take a stance)")
    print(head)
    print("  " + "-" * (len(head) - 2))
    for name, s in all_scores.items():
        c, t = s["overall"]
        cells = [pct(s["strata"][st]) for st in STRATA]
        overall = f"{100*c/t:.0f}%" if t else "-"
        print(f"  {name:{name_w}}   {overall:>6} {c:>2}/{t:<2} " + " ".join(cells))

    print("\n  `complement` is the column that decides this. It is the rows where the")
    print("  paper reports the OPPOSITE exposure to the claim. An overall score that")
    print("  looks fine while that column sits near 50% is the current map.")

    head2 = (f"  {'run':{name_w}}   false stance    bears on?         tier   calls/pair")
    print("\n\n  RELEVANCE — does the paper bear on the claim at all?")
    print(head2)
    print("  " + "-" * (len(head2) - 2))
    for name, s in all_scores.items():
        fc, ft = s["false_stance"]
        print(f"  {name:{name_w}}  {pct(s['false_stance'], 8)} {fc:>2}/{ft:<2}  "
              f"{pct(s['bears'], 8)} {s['bears'][0]:>2}/{s['bears'][1]:<2}  "
              f"{pct(s['tier'], 8)}      {s['calls']:.2f}")

    print("\n  `false stance` is a verdict asserted about a paper the gold set says does")
    print("  not test the claim. LOWER IS BETTER, and a one-call prompt scores 100% by")
    print("  construction — it is never offered the option of declining. That is the")
    print("  number the whole two-call design exists to move.")
    print("  `bears on?` and `tier` are blank for a prompt that reports no relevance.")


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
