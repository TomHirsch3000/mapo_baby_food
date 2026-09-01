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

```
python backend/evaluate_claims.py --all --force --model qwen3-8b-gpu
```

~7,769 pairs at roughly 15 s each, so **26–33 hours**. It is resumable and
commits per row. Rows are processed **best-first globally** (keyword score, then
citations), so stopping early leaves the most useful evidence done for every
claim rather than some claims finished and others untouched.

`qwen3-8b-gpu` is a local Modelfile (`backend/Modelfile.qwen3-8b-gpu`) that pins
`num_gpu 99` and `num_ctx 4096`. On the 6 GB card Ollama otherwise leaves ~2 GB
unused and spills 25% of layers to CPU, which drops throughput from 35 tok/s to
15.6. **On the Mac you do not need this file** — just use `qwen3:8b`.

## What the Mac should do — in this order

### 1. Bake off `gpt-oss:20b`  (~20 minutes, do this first)

This is the question the Windows machine physically cannot answer. 6 GB of VRAM
caps it at an 8B model; the Mac's 24 GB of unified memory fits a 20B comfortably.
Cells 2–4 of the original bake-off table were written off as unreachable — on the
Mac they are reachable.

```sh
git pull
ollama pull gpt-oss:20b
python backend/bakeoff.py --model gpt-oss:20b
python backend/bakeoff.py --score-only        # all runs, side by side
```

**No database needed** — the bake-off reads `gold/gold_set.csv`, which is in git.

Also worth 20 minutes, for a straight hardware comparison on identical work:

```sh
ollama pull qwen3:8b
python backend/bakeoff.py --model qwen3:8b
```

The number to compare is **the complement column against 71%**. Overall accuracy
can look fine while that column sits at chance, and that is precisely the map we
are trying to replace.

**Set `MAX_TOKENS` expectations:** a reasoning model spends tokens thinking
before it emits any JSON. `bakeoff.py` allows 1600 and `evaluate_claims.py` now
matches it. At 450 — the old value — qwen3 failed 2 of 3 pairs outright. If
`gpt-oss:20b` returns unparseable rows, raise the ceiling before concluding it
cannot hold the format.

### 2. Then, depending on the result

**If `gpt-oss:20b` beats 67% / 71%:** it should evaluate the high-stakes claims,
where a wrong verdict does real harm. Fifteen claims carry `if_wrong: serious`
in `gold/claim_audit.csv`; eight of those also cost nothing to follow:

```
back_to_sleep  honey_avoid_12m  soft_bedding_risk  overheating_sids
vitamin_k_birth  blw_choking  swaddle_rolling_risk  walkers_injury
```

That is ~640 pairs for the eight, ~1,360 for all fifteen.

```sh
python backend/evaluate_claims.py back_to_sleep honey_avoid_12m soft_bedding_risk \
    overheating_sids vitamin_k_birth blw_choking swaddle_rolling_risk walkers_injury \
    --force --model gpt-oss:20b
```

**If it does not beat qwen3:** stop. Record the result and let the Windows run
finish. A null result here is worth having — it closes the "would a bigger model
fix it" question that has been open since the bake-off was written.

### 3. Do NOT run `--all` against a shared database

Both machines writing one SQLite file over a share will corrupt it or block.
`evaluate_claims.py` commits per row specifically so that **shards on separate
copies** can be merged later, which is the supported pattern:

```sh
python backend/snapshot_db.py            # -> data/claims-snapshot.db, safe mid-run
python backend/snapshot_db.py --serve    # or hand it over the LAN
```

`data/*.db` is gitignored, so **the Mac will not get the new verdicts from git.**
It needs a snapshot copied across, and only for step 2 — step 1 needs no DB.

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
