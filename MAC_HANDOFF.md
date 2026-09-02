# Mac handoff — 2026-09-02

The Windows laptop is part-way through a full re-evaluation. This is what the
Mac should do, and why.

## What just happened

`mistral` (7B) built the current map. It scores **54%** on the gold set and
**43%** on the complement stratum — the rows where a paper reports the opposite
exposure to the one the claim names ("prone increases SIDS" against a claim that
supine reduces it). Half the complement rows were coin-flips, which is what
inverts a claim on the map.

Four candidates were measured on the 57-row gold set:

| run | overall | complement |
|---|---|---|
| **qwen3:8b / current** | **67%** | **71%** |
| qwen3:8b / decomposed (screen then stance) | 58% | 43% |
| qwen3:8b / polarity v2 | 42% | 43% |
| qwen3:8b / polarity v1 | 29% | 14% |
| mistral / current *(built the live map)* | 54% | 43% |

The two clever designs both lost to simply asking a better model the direct
question, so **the winner is the existing prompt with a better model.** Nothing
about the pipeline changed except which model answers.

Two things worth knowing before trusting those numbers:

- 42 of the 57 gold rows were labelled by a model (Fable), 15 by hand. A blind
  re-label of the 15 hand-labelled rows agreed **80%** on the does-it-test-the-
  claim call and only **2 of 6** on stance. So these are **agreement scores, not
  accuracy**. They rank the candidates against a consistent yardstick, which is
  all the decision needed — but do not put "67% accurate" in a README.
- The gold set is small: 24 scoreable stance rows, 7 of them complement.

## What the Windows machine is doing

Its half of the shard, with the same model the Mac will use:

```
python backend/evaluate_claims.py $(grep -v '^#' shards/windows.txt) --force --model qwen3-8b-gpu
```

3,783 pairs at roughly 15 s each, so **13-16 hours** — half what an unsharded
pass would have cost. Resumable, commits per row.

Within a shard, rows are processed **best-first** (keyword score, then
citations), so stopping early leaves the most useful evidence done across every
claim in that half rather than some claims finished and others untouched.

`qwen3-8b-gpu` is a local Modelfile (`backend/Modelfile.qwen3-8b-gpu`) pinning
`num_gpu 99` and `num_ctx 4096`. On the 6 GB card Ollama otherwise leaves ~2 GB
unused and spills 25% of layers to CPU, dropping throughput from 35 tok/s to
15.6. **The Mac does not need it** — plain `qwen3:8b` is the same weights.

## What the Mac should do — in this order

### 1. Bake off `gpt-oss:20b`  (~20 minutes, do this first)

This is the question the Windows machine physically cannot answer. 6 GB of VRAM
caps it at an 8B model; the Mac's 24 GB of unified memory fits a 20B comfortably.
Cells 2-4 of the original bake-off table were written off as unreachable — on the
Mac they are reachable.

```sh
git pull
ollama pull gpt-oss:20b
python backend/bakeoff.py --model gpt-oss:20b
python backend/bakeoff.py --score-only        # every run, side by side
```

**No database needed** — the bake-off reads `gold/gold_set.csv`, which is in git.

The number to compare is **the complement column against 71%**. Overall accuracy
can look fine while that column sits at chance, and that is precisely the map we
are replacing.

**If it returns unparseable rows, raise `MAX_TOKENS` before concluding it cannot
hold the format.** A reasoning model spends tokens thinking before it emits any
JSON. At 450 — the old value in `evaluate_claims.py` — qwen3 failed 2 of 3 pairs;
at 1600 it failed 0 of 57 on the same prompt and the same model.

### 1a. Result — `gpt-oss:20b` lost, so the Mac half runs `qwen3:8b`

Ran on the Mac, 57/57 rows, **0 unparseable** (so `MAX_TOKENS = 1600` was ample
and the format contingency above never applied):

| run | overall | complement |
|---|---|---|
| qwen3:8b / current *(target)* | 67% | **71%** |
| mistral / current *(built the live map)* | 54% | 43% |
| **gpt-oss:20b / current** | **46%** | **29%** |

On the column that decides it, `gpt-oss:20b` scores **29% — below mistral, and
below chance.** It answered `neutral` on 47 of 57 pairs. That is not a parse
failure: it extracts a real finding and then reasons its way to "does not test
it". It is a genuinely conservative model, and declining to commit scores zero
on a stance benchmark.

This **falsifies the premise of the split in step 2** — "the Mac can hold a 20B
model, so half the corpus gets the better judge". The 20B is not the better
judge. Running the Mac half on it would hand half the corpus to a model worse
than the one that built the map we are replacing.

**So the Mac half runs `qwen3:8b`** — same weights as the Windows
`qwen3-8b-gpu`, differing only in the tag recorded in `evaluated_by`. Two
consequences, both good:

- It matches the sanity check already written into the merge section below,
  which expects `evaluated_by = 'qwen3:8b'` on every Mac row.
- **The cross-shard model effect disappears.** The worry in step 2 — that claim
  A at +0.4 against claim B at +0.6 partly reflects which machine ran it — does
  not arise when both halves share a judge. netSupport becomes comparable across
  the whole map, not just within a claim.

`shards/mac.txt` has had its `# model:` line updated to match, because
`--coverage` reads it and would otherwise report the half as 0% done and raise a
false "the shards overlapped" alarm.

### 2. Then take the Mac half of the pass — with `qwen3:8b` (see 1a)

```sh
python backend/evaluate_claims.py $(grep -v '^#' shards/mac.txt) --force --model qwen3:8b
```

`shards/mac.txt` and `shards/windows.txt` split the 78 claims into disjoint
halves, balanced by **pair** count — 3,784 against 3,783 — because claims run
from 10 papers to 139 and splitting by claim count would be badly skewed. They
are committed rather than regenerated per machine so the two halves cannot drift
apart.

**Both halves are judged by the same model** (`qwen3:8b` on the Mac,
`qwen3-8b-gpu` on Windows — identical weights, different tag). The original plan
gave the Mac half to `gpt-oss:20b` on the theory that a 20B would judge better;
the bake-off in 1a showed it judges worse, so that plan was dropped.

The prompt and the objective are identical on both sides — same `STANCE_PROMPT`,
same `tested_text()` wording, same validation. Only the model differs, and
`evaluated_by` records which one on every row.

The consequence to keep in mind: within a claim, every paper is judged by one
model, so each claim's own netSupport is internally consistent. What carries a
model effect is *comparison between* claims, and the map encodes netSupport as
position — so claim A at +0.4 against claim B at +0.6 partly reflects which
machine ran it. That is why the logging matters, and why the fix if it ever
looks wrong is cheap: re-run one shard on the other model.

Check the split landed as intended once it finishes:

```sh
python backend/evaluate_claims.py --coverage
```

`qwen3:8b` failed 0 of 57 rows at `MAX_TOKENS = 1600` in the 1a bake-off, so the
format contingency in step 1 should not come up on this half.

### 3. Do NOT run `--all`, and do not share one database file

Both machines writing a single SQLite file over a share will block or corrupt
it. Each works on its own copy; the shards are disjoint so the halves can simply
be stitched back together afterwards.

```sh
python backend/snapshot_db.py            # -> data/claims-snapshot.db, safe mid-run
python backend/snapshot_db.py --serve    # or hand it over the LAN
```

`data/*.db` is gitignored, so **the Mac will not get verdicts from git.** It
needs a snapshot copied across — and only for step 2. Step 1 needs no database
at all.

**Merging afterwards.** Because the two halves touch disjoint `claim_key` sets,
the merge is an attach-and-copy rather than a reconciliation — no row is written
by both machines, so there is nothing to resolve:

```sql
ATTACH 'mac-snapshot.db' AS mac;
UPDATE claim_papers AS t
   SET stance = (SELECT m.stance FROM mac.claim_papers m
                  WHERE m.claim_key = t.claim_key AND m.paperId = t.paperId),
       -- ...and the other verdict columns, including all three provenance ones
 WHERE t.claim_key IN (<the mac shard>);
```

Sanity-check before trusting it: every row in the Mac half should come back with
`evaluated_by = 'qwen3:8b'` and a `claim_text_used` matching the current
registry. Any row that does not is either stale or was judged against wording
that has since changed.

## Provenance — read this before overwriting anything

`claim_papers` now carries three new columns, and the old pass is preserved
whole in the table `eval_mistral_202608`:

| column | holds |
|---|---|
| `evaluated_by` | the model tag, e.g. `qwen3-8b-gpu`, `gpt-oss:20b` |
| `prompt_version` | `current`, `polarity`, … |
| `claim_text_used` | **the exact sentence that was judged** |

That third column is the important one. **Twelve claims were reworded on
2026-09-01, and two of them inverted outright** (`bilingual_no_delay`,
`crawling_not_required` — both were negations, now phrased positively so the
evidence can refute them). Comparing an old verdict with a new one on those
claims is comparing answers to different questions, and only `claim_text_used`
makes that visible. Any new pass must write all three.

## Resuming a half-finished pass — `--stale` is not safe on this database

**Symptom if you get this wrong: the run reports success having done almost
nothing, and most of the shard stays on the old model.**

`--stale` resumes on `direction IS NULL`, and the comment above it in
`evaluate_claims.py` explains why that is sound: only the current evaluator
writes `direction`, so a row holding one has been judged under the present
taxonomy. That is not true of this database. The Aug-26 mistral pass populated
`direction` on **2,703 of the Mac shard's 3,784 rows** — values like `agrees`,
`disagrees`, `both`. `--stale` reads all of them as done.

Measured on the paused Mac shard at 1,080/3,784 complete:

| resume flag | pairs it would run | outcome |
|---|---|---|
| `--stale` | **1** | 2,703 rows silently left on mistral, run exits "complete" |
| `--force` | 3,784 | correct, but redoes ~6 h of finished work |
| reset + `--stale` | **2,704** | correct, keeps the 1,080 already done |

The reset clears `direction` on rows the current pass has not itself written,
which restores the invariant the flag assumes:

```sql
UPDATE claim_papers SET direction = NULL
 WHERE claim_key IN (<the shard>)
   AND (evaluated_by IS NULL OR evaluated_by != 'qwen3:8b');
```

`backend/resume_mac_shard.sh` does this and then resumes under `caffeinate`.
Verified on a throwaway copy before use: 2,704 to run, 1,080 preserved, 0 rows
of the Windows shard touched. Take a copy first regardless — the run in progress
was backed up to `data/claims.pre-resume-backup.db`.

**The same trap applies to the Windows half.** Its 9 rows with a null
`direction` are pre-existing — papers mistral never judged — so a `--stale`
resume there would run those 9 and skip the rest of the shard.

The durable fix is for the resume filter to key off `evaluated_by != <model>`
rather than `direction IS NULL`, which asks the question actually being asked:
"has *this* model judged this row?". That is left alone here on purpose — the
Windows pass is mid-flight and changing row selection under it is not worth the
risk. Worth doing once both halves land.

## Moving verdicts between the machines

Two mechanisms, doing different jobs. Both are in git; neither replaces the
other.

**`data/claims-snapshot.db` — the whole corpus, for bootstrapping.** Already
committed, already the documented route, and better than it looks: `VACUUM INTO`
lays pages out deterministically, so git deltas successive versions rather than
storing a fresh copy. An earlier draft of this section claimed the opposite and
was wrong. Refresh it with `python backend/snapshot_db.py`; a second machine
gets the entire corpus — abstracts included — without re-importing from OpenAlex.

What it cannot do is take writes from two machines at once. It is one binary
blob at one path, so when both halves of a sharded pass commit it, git can offer
only take-mine-or-take-theirs, and either answer discards a shard.

**`data/verdicts/<shard>.csv` — the verdicts, for a pass in flight.** One file
per file in `shards/`, partitioned exactly the way the work is, so each machine
writes only its own and concurrent commits from both halves cannot conflict.

Partitioning is the whole point, and a single sorted CSV would not have worked:
the shards interleave alphabetically — `baby_led_weaning` (mac),
`back_to_sleep` (windows), `background_tv` (windows), `bilingual_no_delay` (mac)
— so both machines' edits would land inside each other's diff hunks. Splitting
by shard is what makes the disjointness the pass already has legible to git.

| artifact | size | role |
|---|---|---|
| `data/claims.db` | 25.9 MB | working copy, gitignored, authoritative |
| `data/claims-snapshot.db` | 25.1 MB | whole corpus; deltas well; one writer |
| `data/verdicts/mac.csv` | 1.27 MB | 3,784 rows; the Mac writes only this |
| `data/verdicts/windows.csv` | 1.27 MB | 3,783 rows; Windows writes only this |

### What the Windows machine should do

Nothing yet — but when its half finishes, or any time it wants to publish
progress:

```sh
git pull
python backend/export_verdicts.py --shard windows   # -> data/verdicts/windows.csv
git add data/verdicts/windows.csv && git commit -m "windows shard verdicts" && git push
```

To take this machine's half:

```sh
git pull
python backend/export_verdicts.py --import data/verdicts/mac.csv --dry-run
python backend/export_verdicts.py --import data/verdicts/mac.csv
python backend/evaluate_claims.py --coverage
```

An import matches on `(claim_key, paperId)` and writes only the verdict columns,
so taking the Mac half cannot disturb the Windows half. A pair in the file that
does not exist locally is reported, not inserted — that means the corpora have
diverged and is worth knowing rather than papering over.

Round-trip is lossless bar one forced normalisation: CSV cannot distinguish an
empty string from NULL, so a `""` returns as NULL. Verified by wiping a shard
from a copy and restoring it — 7,767 of 7,769 rows identical, both exceptions an
empty `stance_summary`.

**Note for whoever imports first:** the Mac's `windows.csv` currently shows 0
judged. That is not a claim about the Windows run — this machine's database is
the Aug-26 copy, which predates the provenance columns, so it simply has no
verdicts for that half. Windows should export its own rather than treat the
Mac's file as authoritative for its claims.

### 202 pairs belong to no shard, and that is deliberate

`motor_cognitive_link` (139 pairs) and `responsive_interaction` (63) are in
`claim_papers` but in neither shard and not in the registry: both were dropped
on 2026-08-31 as unfalsifiable, with their papers kept on purpose
(`gold/dropped_claims.md`). The exporter now names them, and shouts separately
if a claim that IS still live turns up in no shard — that one would mean nothing
is going to evaluate it.

## What is NOT done

- **`build_claims_data.py` has not been run** on the new verdicts. Nothing is
  live yet.
- The frontend and exporter are untouched — this pass changes no JSON shape.
- `stated_position`, relevance tiers and the netSupport gate ([D25](DECISIONS.md))
  are decided and gold-labelled but **not implemented**. That is a separate
  project needing exporter and frontend work; it is not part of this pass.
- `gold/claim_audit.csv` has 13 stakes rows flagged `uncertain` and 7 claims
  where NHS and AAP guidance disagree, both awaiting a human call.
