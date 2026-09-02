# Where we got to — 2026-09-02

Paused mid-pass. This is what is running, what was decided, and what to do next.

Branch: `claim-schema-and-bakeoff`, pushed. Both machines are on it.

---

## Both halves PAUSED — nothing is running

| machine | model | shard | progress |
|---|---|---|---|
| Windows | `qwen3-8b-gpu` | `shards/windows.txt` — 39 claims | **1,488 / 3,783 (39%)** |
| Mac | `qwen3:8b` | `shards/mac.txt` — 39 claims | **1,080 / 3,784 (29%)** |

Stopped deliberately on the evening of 2026-09-02, not crashed. The evaluator
commits per row, so at most one pair was lost. Both halves are exported to
`data/verdicts/*.csv` and pushed, so the progress survives even if a database is
lost.

Power settings were restored by hand (standby 900, hibernate 10800, AC and DC) —
force-killing the keep-awake watcher skips its `finally` block, so a future
watcher should be stopped gracefully or the settings checked afterwards.

**Roughly 2,300 windows pairs and 2,700 mac pairs remain**, about 9 h and 11 h
respectively at 15 s/pair.

The pass commits per row, so an interruption loses at most one pair.

**Resuming is NOT `--stale`, and NOT dropping `--force`.** Both silently do
almost nothing. The Mac hit this on its own half:

- `--stale` selects on `direction IS NULL`, which is sound only while this
  evaluator is the only thing that ever wrote that column. The Aug-26 mistral
  pass already filled `direction` on most rows, so `--stale` reads them as
  finished. **Measured on the Windows shard: it would run 1 pair, print its
  normal completion line, and leave 2,402 rows still judged by the model this
  pass exists to replace.** Nothing about that failure looks like a failure
  afterwards, which is what makes it worth writing down.
- Dropping `--force` skips rows that already carry a stance — and mistral gave
  every row a stance, so it skips nearly all of them.

The question actually being asked is *"which rows has this model not judged
yet"*. So resume by clearing `direction` wherever `evaluated_by` is not the
model being run, then using `--stale`. `backend/resume_mac_shard.sh` does that
for the Mac. The Windows equivalent is the same two steps:

1. `UPDATE claim_papers SET direction = NULL WHERE claim_key IN (<windows shard>)
   AND evaluated_by IS NOT 'qwen3-8b-gpu'`
2. `python backend/evaluate_claims.py $(grep -v '^#' shards/windows.txt) --stale --model qwen3-8b-gpu`

Run step 1 against a **copy** of the DB first, as the Mac did. The check is
cheap: the number of rows it queues should match what `--coverage` reports as
outstanding for that shard, and no row outside the shard should be touched.

Progress, any time:

```sh
python backend/evaluate_claims.py --coverage
```

The honest fix is for `--stale` to select on `evaluated_by != model` rather than
on `direction`. Deliberately not done while a pass is in flight — changing row
selection underneath a running job buys nothing.

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

**First data, from the Mac shard paused at 1,080/3,784 — and it points the other
way.** `bilingual_no_delay` is 14/118 judged: **4 refutes, 3 mixed, 1 supports,
6 neutral**. That is a 29% refutes rate on the claim written to be refutable,
against 2.8% across the shard as a whole. An order of magnitude apart, on
precisely the claim where the difference was predicted.

A model that cannot say no does not say it ten times more often exactly where
the evidence should make it. So refutes-aversion is no longer the leading
explanation, and the `gpt-oss:20b` result — neutral on 47 of 57 — may say more
about that particular model than about the task.

Still early: 14 rows, and `crawling_not_required` has none yet.

### Re-read with both shards merged — largely resolved (BACKLOG 23a)

2,548 pairs judged, 43 claims now have enough directional verdicts to read:

| | yesterday, 19 claims | now, 43 claims |
|---|---|---|
| net **negative** (refuted) | 0 | **2** |
| 0 to +0.49 (contested) | 0 | **4** |
| +0.50 to +0.99 | 11 | 21 |
| +1.00 | 8 | 16 |

`blw_choking` is at **-1.00** (0 supports, 6 refutes) and `bilingual_no_delay` at
**-0.60** — the claim rewritten to be refutable is being refuted. **The designed
test passes.** Yesterday's "nothing is refuted" was best-first ordering putting
the well-supported claims first, not a model that will not say no.

**The export is no longer blocked on this.** Finish both shards, re-read that
table, then run `build_claims_data.py`.

Still worth watching: corpus-wide refutes is 2.7% against mistral's 20.2%, and
neutral 68% against 31%. Most of that drop is correct — mistral gave hard
verdicts to 22 of 32 off-topic gold papers and qwen3 to 2 — but "correctly
declined" and "would rather not say" remain indistinguishable in the data, which
is D25's relevance tier again.

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
