# Where we got to — 2026-09-02

Paused mid-pass. This is what is running, what was decided, and what to do next.

Branch: `claim-schema-and-bakeoff`, pushed. Both machines are on it.

---

## Running right now — leave it alone

| machine | model | shard | progress | eta |
|---|---|---|---|---|
| Windows | `qwen3-8b-gpu` | `shards/windows.txt` — 39 claims | **1,375 / 3,783 (36%)** | ~10 h |
| Mac | `qwen3:8b` | `shards/mac.txt` — 39 claims | starting | ~10-15 h |

**Do not close the Windows laptop's lid.** Sleep is disabled by a background
watcher that restores the original settings (standby 900, hibernate 10800) when
the pass ends, and leaves the machine on. Lid action was not readable on this
machine so it could not be overridden — closing the lid still suspends and kills
the run.

The pass is resumable and commits per row. If it dies, re-running the same
command picks up where it stopped without redoing finished rows (drop `--force`,
or use `--stale`).

```sh
python backend/evaluate_claims.py $(grep -v '^#' shards/windows.txt) --force --model qwen3-8b-gpu
python backend/evaluate_claims.py --coverage      # progress, per shard, any time
```

**Nothing is live.** `build_claims_data.py` has not been run, so the site still
serves the mistral map. Do not export until the open question below is settled.

---

## What was decided

**The winner is the prompt that was already there.** Four candidates on the
57-row gold set:

| run | overall | complement |
|---|---|---|
| **qwen3:8b / current** | **67%** | **71%** |
| qwen3:8b / decomposed (screen then stance) | 58% | 43% |
| mistral / current *(built the live map)* | 54% | 43% |
| gpt-oss:20b / current *(Mac)* | 46% | 29% |
| qwen3:8b / polarity v2 | 42% | 43% |
| qwen3:8b / polarity v1 | 29% | 14% |

Both clever designs lost to asking a better model the direct question. The pass
running now is the existing `STANCE_PROMPT` with a better model, nothing else.

**[D25](DECISIONS.md#d25)** — `stated_position` as a third axis, kept out of
`netSupport`. A paper that assumes a claim is not evidence for it.

**Registry finished (BACKLOG 1d).** All 78 claims now carry `claim_type`,
`claim_sign`, `claim_exposure`, `claim_outcome`. Twelve were reworded, two
inverted outright (`bilingual_no_delay`, `crawling_not_required` — negations
rewritten as positive assertions so evidence can refute them). Two were dropped
as unfalsifiable, archived in `gold/dropped_claims.md`.

**Gold set finished.** 57 rows, three axes, provenance recorded in `labelled_by`.

**Guidance sourced.** All 78 claims against NHS and AAP, **118 of 119 quotes
re-fetched and proved present on the page**; the one that could not be verified
was dropped rather than shown with a caveat. Seven claims where the two bodies
disagree.

---

## The open question — read this before shipping

**BACKLOG item 23.** 36% into the pass, refutes have collapsed 88%:

| | mistral | qwen3 |
|---|---|---|
| supports | 681 | 389 |
| refutes | **313** | **37** |
| neutral | 325 | 908 |

Of 19 claims with five or more directional verdicts, **none reads as refuted and
none as contested.** `honey_avoid_12m` moved from −0.01 to **+0.92** and
`back_to_sleep` from +0.23 to **+1.00**. That is the direction BACKLOG item 1
asked for — those are settled facts the map was reading as contested — but item 1
predicted +0.20, not +1.00.

A map that cannot refute anything is as uninformative as one that contests
everything, and it cannot do the thing a parent most needs: say that a
widely-believed claim is not supported.

**The Mac's bake-off made this a diagnosis rather than a suspicion.**
`gpt-oss:20b` answered `neutral` on **47 of 57** gold pairs — a larger, more
careful model scoring below mistral purely by declining to take a position. So
neutral-aversion is not a qwen3 quirk; it is what a careful judge does on this
task. Nothing in the pipeline currently separates *"this paper does not test the
claim"* from *"I would rather not say"* — which is exactly what D25's `relevance`
tier was designed to draw, so D25 is now part of the accuracy work rather than a
later feature.

### The test that settles it

`bilingual_no_delay` and `crawling_not_required` were rewritten as positive
assertions **specifically so the evidence could refute them**. Both are in the
Mac shard. When it finishes:

```sh
python - <<'PY'
import sqlite3
c = sqlite3.connect('data/claims.db')
for k in ('bilingual_no_delay', 'crawling_not_required'):
    print(k, c.execute("""SELECT stance, COUNT(*) FROM claim_papers
                          WHERE claim_key=? AND evaluated_by LIKE 'qwen3%'
                          GROUP BY stance""", (k,)).fetchall())
PY
```

If neither comes back refuted, "the claims really are all settled" is dead and
the pass has overcorrected.

---

## Next session, in order

1. **Check both shards finished** — `python backend/evaluate_claims.py --coverage`.
   It reports progress per shard and flags the one failure the shards exist to
   prevent: a claim touched by both machines.
2. **Merge the Mac's half back.** The shards are disjoint, so it is an
   attach-and-copy, not a reconciliation — see MAC_HANDOFF.md §3.
3. **Run the refutes test above.** This gates everything after it.
4. **If it passes**, run `build_claims_data.py`, eyeball `topics.json`, ship.
5. **If it fails**, do not ship. The likely fix is D25's relevance tier, which
   lets a paper say "not about this" instead of hiding in `neutral`.

## Still waiting on you

- `gold/claim_audit.csv` — **13 stakes rows flagged `uncertain`** (mostly cost
  that depends on the family, not the claim) and **7 claims where NHS and AAP
  disagree**. Add any column you like; `build_audit_table.py` carries unknown
  columns forward on re-run, keyed on `claim_key`.
- `physical_activity_guideline` is the one real duplicate found — its `tested_as`
  dropped the "30 minutes daily" threshold, collapsing it into `tummy_time_motor`.
  Independently, the dose is exactly where NHS and AAP disagree on it.
- `cost_varies` flag for the circumstance-dependent stakes rows, if you want it.

## Caveats worth not forgetting

- **The gold scores are agreement, not accuracy.** 42 of 57 rows were labelled by
  a model. A blind re-label of your 15 agreed 80% on does-it-test-the-claim and
  **2 of 6** on stance. Fine for ranking candidates against a consistent
  yardstick; not fine for a README.
- **The gold set holds ~5 scoreable `refutes` rows** — too few to have caught a
  model that never says no, which is the failure this pass may have introduced.
- **`MAX_TOKENS` must stay in step between `evaluate_claims.py` and
  `bakeoff.py`.** At 450 qwen3 failed 2 of 3 pairs; at 1600, 0 of 57. Found by a
  smoke test about a minute before a 33-hour run started.
