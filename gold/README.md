# Gold set — the measurement that gates the re-run

`gold_set.csv` is 60 hand-labelled (claim, paper) pairs. It exists so that
"is this prompt better?" becomes a ten-minute measurement instead of an
overnight run and an impression. Backlog item **1a**; everything in P0 depends
on it.

## What to fill in

Two columns, per row. Everything to the right of the `--` divider is the
**current model's answer** — read it *after* you have formed your own, or it
will anchor you.

### `YOUR_relevance` — what did this paper measure?

Take the FIRST tier that fits. This is about **what was measured, never about
whether the findings agree.** A paper that destroys the claim is `direct`.

| Value | Means |
|---|---|
| `direct` | tests the claim: its population, its exposure, its outcome |
| `indirect` | tests a neighbouring question — older population, animal model, proxy outcome, related dose or route |
| `framework` | does not test the claim, but supplies a method, measure, definition, mechanism or guideline that papers testing it would use |
| `background` | mentions the topic, contributes nothing |

#### Telling `framework` from `background`

Both mean "does not test the claim". The difference is whether it hands the people
who *do* test it something to work with.

**The test:** can you name what it offers in one word — method, measure, definition,
mechanism or guideline? If you are straining, it is `background`. `framework` has to
be earned; used loosely it becomes a bin for "interesting but does not fit", which is
exactly how the old context box filled up with misfits.

**The sharper version, for borderline cases:** *would a paper testing this claim cite
it in its Methods section?* `framework` papers get cited in Methods — this is the
instrument we used, this is how we defined the outcome. `background` papers get cited
in a throwaway intro sentence, or not at all.

> A tablet-based assessment of cognitive control in 18-24-month-olds, against the claim
> *"educational apps improve learning outcomes in toddlers"* → **`framework`**, offers a
> **measure**. A trial needs some way to measure learning in a pre-verbal child; this is one.

**Mechanism is the tricky one**, because it feels relevant whenever it concerns the same
outcome. A tool only counts if it serves *this* claim:

- a mechanism for the claim's **exposure → outcome pathway** → `framework`
- a mechanism for the **outcome in general**, bypassing the claim's exposure → `background`

> A "wear and tear" hypothesis of SIDS aetiology — cumulative stress from in utero
> onward — against the claim *"back sleeping reduces SIDS"* → **`background`**. It is a
> theory of the outcome that says nothing about sleep position, so nobody testing sleep
> position gets a tool from it.

### `YOUR_stance` — which way does it point?

Only for `direct` and `indirect`. Leave blank for the other two.

| Value | Means |
|---|---|
| `supports` | findings agree with the claim |
| `refutes` | findings disagree with it |
| `mixed` | findings point **both ways** |
| `neutral` | tested it and could not tell — underpowered, null with wide intervals |

**The case that matters most.** Where a paper reports the *complement* of the
claim's exposure, work it through rather than matching words:

> Claim: "Placing infants on their back to sleep reduces the risk of SIDS"
> Paper: "Prone and side sleeping increase the risk of SIDS compared to supine"
> → prone is the opposite of back sleeping, and it *increases* the risk
> → therefore back sleeping *reduces* it → **supports**

15 of the 60 rows are this shape. They are the known failure mode and they are
what the whole measurement is for.

Use `YOUR_notes` freely — especially where you hesitated. A row you found
genuinely ambiguous is not a model failure, and the scoring should know that.

## Then — running the bake-off

`backend/bakeoff.py` runs the set through a model and scores it against your
labels. Resumable per row, so a run can be killed and restarted; results cache
to `gold/runs/<model>__<prompt>.json` and scoring never re-runs anything.

```sh
# no labels needed - see how a model differs from what is stored
python backend/bakeoff.py --model gpt-oss:20b --compare

# the real thing, once YOUR_stance is filled in
python backend/bakeoff.py --model gpt-oss:20b
python backend/bakeoff.py --model qwen3.6:27b --prompt decomposed

# score every run held, without running anything
python backend/bakeoff.py --score-only
```

The `complement` stratum is scored separately, and it is the column that
decides this. An overall accuracy that looks respectable while those 15 rows
sit near 50% is exactly the number that produced the map as it stands.

| # | Model | Prompt | |
|---|---|---|---|
| 1 | `mistral:7b` | current | already in `model_stance` — free baseline, no run needed |
| 2 | `gpt-oss:20b` | current | does size alone fix it? |
| 3 | `gpt-oss:20b` | decomposed | does structure fix it? |
| 4 | `qwen3.6:27b` | decomposed | does the last of the Mac's headroom help? |
| 5 | Claude, in a Claude Code session | current | the ceiling — is this hard for everyone? |

Nothing here touches the live pipeline. To point the real evaluator at a
different model once you have picked one, it already takes a flag:

```sh
python backend/evaluate_claims.py cow_milk_12m --model gpt-oss:20b --force
```

## Notes

- Sampling is seeded (`20260829`), so regenerating produces the same 60 pairs.
  Re-run the generator only if you want a different sample; your labels are not
  recoverable if you do.
- Rows are shuffled after stratification so the stratum is not inferable from
  position. `stratum` is recorded at the far right for scoring.
- 41 of the 80 claims are represented.
