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

## What is NOT done

- **`build_claims_data.py` has not been run** on the new verdicts. Nothing is
  live yet.
- The frontend and exporter are untouched — this pass changes no JSON shape.
- `stated_position`, relevance tiers and the netSupport gate ([D25](DECISIONS.md))
  are decided and gold-labelled but **not implemented**. That is a separate
  project needing exporter and frontend work; it is not part of this pass.
- `gold/claim_audit.csv` has 13 stakes rows flagged `uncertain` and 7 claims
  where NHS and AAP guidance disagree, both awaiting a human call.
