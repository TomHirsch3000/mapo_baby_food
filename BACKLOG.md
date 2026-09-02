# Backlog

**Status:** the ordered list of everything the restructure discussion generated.
Nothing here is implemented. `DECISIONS.md` holds what was measured and why it was
chosen; `backend/prompts_v2.py` holds the draft prompts. This file is the running
order, and it shrinks as work completes.

Rule for using this document: **one item at a time.** Items are ordered so that
each one is finishable without the ones below it. Where that is not true it is
stated explicitly under *Blocked by*.

---

## P0 — Correctness. Nothing else is worth building on top of this.

### 1. The paper-to-claim interpretation is wrong often enough to invert claims

**The problem, measured.** Net support among each claim's *best* papers (top
quartile by design x citations):

| Claim | net (all papers) | net (best papers) |
|---|---|---|
| `back_to_sleep` | +0.21 | **-0.02** |
| `vitamin_k_birth` | +0.03 | **-0.04** |
| `salt_limit` | +0.24 | **-0.02** |
| `honey_avoid_12m` | -0.05 | **-0.20** |

Back-to-sleep and vitamin K at birth are two of the most settled facts in
paediatrics. The map currently reads them as contested.

**Two distinct causes**, established by reading the top refuting papers on
`back_to_sleep`:

- **Polarity inversion.** The model writes a correct finding and then flips the
  direction. "Prone and side sleeping increase the risk of SIDS compared to
  supine" is stored as REFUTES the claim "back sleeping reduces SIDS risk". It
  matched on the word "increase".
- **Relevance leakage.** Papers on serotonergic receptor binding, sudden death
  in epilepsy, and bed-sharing are scored `refutes` on a sleep-position claim.
  They do not test it at all.

**Scale.** ~13% of refutes-rows across the 12 protective-framing claims assert
an *increased* risk in their own stored finding text. On `back_to_sleep`,
correcting the 9 mechanically-detectable inversions moves the best-evidence
reading from **-0.02 to +0.20**.

**The decisive measurement.** Of the `back_to_sleep` findings that report the
complement exposure ("prone increases risk" rather than "supine reduces risk"):

```
already scored supports (model handled the flip)   9
scored refutes (model inverted)                    9
```

Exactly half. The model is not applying a rule badly; it is not applying a rule.
This is why a patch that flips on "exposure is opposite" cannot work — it would
break as many rows as it fixes.

**Sub-items, in order:**

| # | Item | Notes |
|---|---|---|
| 1a | **Gold set** — 60 hand-labelled pairs — **built**, see `gold/` | Stratified across tiers, stances, and *deliberately including complement-exposure cases*. Turns "is this prompt better" from an overnight run and an impression into a ten-minute measurement. Prerequisite for everything below it. |
| 1b | **Model bake-off** — harness **built**, `backend/bakeoff.py` | Current stack is `mistral` (7B). Hardware caps local at ~20B (16 GB GPU) or ~27B (24 GB Mac), so a frontier model is not reachable locally — which means prompt structure is the only lever that can actually be pulled. Five cells; costs an evening and nothing. |
| 1c | **Decomposed stance prompt** | Model answers `effect` / `exposure_polarity` / `outcome_polarity`; stance is computed in Python against a per-claim `claim_sign`. See `prompts_v2.py`. |
| 1d | **Registry columns** — `claim_sign`, `claim_exposure`, `claim_outcome`, `population` | 80 rows, hand-checked once. One wrong sign flips an entire claim, so this gets eyeballed as a printed table. `population` is what the screen prompt compares a paper's sample against — without it the model infers the claim's population from the sentence, differently each time. |
| 1e | **Two-call screen/stance split** | Drafted in `prompts_v2.py`. See the three consequences below the table. |
| 1f | **Full re-run** | Hours locally, or minutes and ~$40 on a hosted model. Do not start until 1a–1e are settled — SPEC §6 is explicit that the taxonomy is frozen before a pass, not during one. |

**Three consequences of the two-call split (1e) worth stating explicitly:**

- **It roughly pays for itself.** ~31% of pairs never reach the stance call at all,
  so the cheap screen gates the expensive judgement rather than adding to it. It also
  gives a small model one job at a time, which is the only way it does either well.
- **`neutral` narrows to something true.** It stops being the drain for everything
  unmatched and becomes only *"tested this and could not tell"*. Background papers
  never reach the stance question, so nothing they might have said can leak into a
  verdict. That is most of what makes today's `neutral` bucket meaningless.
- **The two stages become independently re-runnable.** Re-scoring stance on a new
  model no longer means re-deciding relevance, and vice versa. At 14-25 hours a pass,
  that is worth the extra parse surface on its own.

**Extract the age window on every paper, not only on timeline claims.** It is a
relevance signal everywhere — a study of five-year-olds is `indirect` for an infant
claim — and there will not be a cheap second chance to collect it. The columns are
listed at the foot of `prompts_v2.py`.

**Open question under discussion:** whether the decomposition is the right shape,
or whether a stronger model makes it unnecessary. 1a + 1b answer this by
measurement rather than by argument.

---

### 2. `paper_weight` is called with the wrong argument

[`build_claims_data.py:314`](backend/build_claims_data.py#L314) computes the
exported per-paper `weight` as `paper_weight(row["evidence_strength"], ...)`,
but the first parameter is `study_type`. Line 154 — the claim-level maths —
passes it correctly.

`design.rank_of("strong"|"moderate"|"limited"|"mixed")` all fall through to the
0.30 unclassified default, so **every paper's exported weight is computed as if
its design were unknown**. The number already sitting on the card's data is not
the number driving the claim's position.

Small, independent of item 1, and every numeric feature below sits on it. Do it
whenever there is a spare ten minutes.

---

## P1 — Structure. Needs the re-run to have happened.

### 3. Relevance filter replaces the readings toggle

Retire conservative / balanced / liberal as a control; ship `balanced` as the
layout. `mixed` is 196 of 7,769 pairs (2.5%), and the largest count on any one
claim is 9 of 192 — so the most prominent control on screen moves the picture on
a handful of claims and does nothing on the rest.

Keep computing all three nets. Where they diverge by more than ~0.15, **state it
on the claim** rather than making the reader operate it: *"reads +0.6 to -0.1
depending on how its two-sided papers are counted."*

The freed control becomes **direct only / direct + indirect / everything**.

*Open:* how much `indirect` is discounted. Not a flat multiplier — a paper is
indirect for a stated reason (older population / animal model / proxy outcome /
different dose / different route) and those do not discount equally. Store the
reason as an enum, set the discounts against the gold set.

**Blocked by:** 1.

---

### 4. Framework papers become "How this question is tested"

**Decided: keep them, stop rendering them as cards.**

The reasoning (Tom's — `DECISIONS.md` D10 has it in full): a
single result is dismissible as a one-off, but the shared method behind a body
of work is what makes it persuasive. *It is not only what they discovered, it is
how they discovered it.* That is an argument about changing someone's mind, which
is what the map is for.

Today they land in the context box by **failure** — a paper is there for not
fitting anywhere else, and then wins a citation contest among the other misfits.
Under the screen pass a paper enters only if it is tiered `framework` **and** the
model can name what it offers (method / measure / definition / mechanism /
guideline), **and** it clears the existing relative citation bar.

Render as a claim-panel section, not as grey rectangles parked outside the plot
where position encodes nothing:

> **How this question is tested**
> · Double-blind placebo-controlled food challenge — the diagnostic standard *(Sampson 2012, cited by 34 of these papers)*
> · SCORAD severity index — how eczema severity is scored here *(cited by 19)*

Each one carries its `relevance_reason` where the reader can see it, so the answer
to *"why is this paper here?"* is on the page rather than inferred — the same
auditability rule stances are already held to (Principle 4).

Default **on**. Everything tiered `background` is dropped and reported as a
count — *"N of M papers collected did not address this claim"* — which is a
genuinely useful statement about retrieval quality.

**Blocked by:** 1.

---

## P2 — Transparency of the formula.

### 5. Per-card influence

Two signed numbers per card: how far this paper pulls the claim vertically
(support) and horizontally (quality).

**Computed as leave-one-out deltas**, not as a "share of the total". The
horizontal one has no per-paper share to compute — `evidence_quality_of` is
`0.5 x mean(top quartile) + 0.35 x mean(top decile) + 0.15 x mean(all)`, so a
paper outside the top quartile contributes only through the 0.15 term.
Leave-one-out is exact for any formula, survives the next change to the
weighting, and is literally the question the reader is asking.

**And it is cheap**, which is not obvious — recomputing a claim once per paper sounds
expensive. 80 claims x ~150 papers is a five-figure number of arithmetic operations,
done once at build time.

The wording has to respect that leave-one-out influences **do not sum to the
total** (the denominator moves): *"remove this paper and the claim moves 4 points
down"*, never *"this paper contributes 4 points"*.

**Units.** Both numbers in axis points, signed, on the same 0-100 scale the reader is
already looking at: Y on the -100..+100 support axis, X on the 0..100 quality axis.
Round to integers — a sub-point influence reads as 0, which is true.

**Space is the constraint.** The design label already only appears at `w >= 124`.
Compact form, rank staying dominant:

```
   #7          <- unchanged, largest
  ↑4  →2       <- signed influence, tiny, one row
```

**Consequence to design around:** on a 150-paper claim, ~145 cards read `0`.
That is the true picture — a claim is usually decided by five papers — but two
numbers that are almost always zero is transparency nobody reads. So ship both:

- **micro-vector on every card** — a 2–3px tick up/down and left/right from the
  card centre, length proportional to influence. Reads without focusing,
  degrades gracefully on the smallest cards, and is a miniature of the map the
  card is sitting on. Digits on hover.
- **"What is holding this claim up" — top 5 movers on the claim panel.** This is
  the one a reader will actually use, and it is what SPEC §3.3 already promises
  about heavily-cited studies pulling a verdict away from the bulk.

**Blocked by:** 2 (the weight must be correct before it is shown).

---

### 6. Contested claims — leftward whisker

**Decided: do not move the dot.**

X means study-design quality. Pushing a contested claim left would make X mean
"how much you can rely on the answer" — after which *"nobody has run a good
study"* and *"two good studies disagree"* land on the same coordinate. For a
parent those are opposite situations: one says wait, the other says the question
is genuinely open.

Instead: the dot stays at its true quality X and grows a horizontal whisker
reaching left to where it *would* sit if disagreement were discounted. The reader
sees both numbers and the gap. Fallback if the whisker reads as noise: a split
or hatched dot, before it is a moved one.

Vertical centring needs no mechanism — `net = (S-R)/(S+R)` already puts a strong
supporter and a strong refuter mid-height.

**Measure contestedness among the good papers only.** `consensus = |netSupport|`
is too crude: fifty weak studies disagreeing is not a contested claim, it is an
unstudied one. Reuse the top-quartile / top-decile machinery in
`evidence_quality_of` so it reads *"the best evidence here does not agree"*.

**Blocked by:** 1 — see the table at the top of this file. Today's contested
claims are mostly classification errors, so this would ship as a bug reporter.

---

### 7. Links between opposing papers

**Rejected: citation edges as a rebuttal proxy** (`DECISIONS.md` D8). Proposed as the
free, high-precision option. Measured: opposite-stance citation edges
are **1,942 of 12,318 — 16% of all edges**, median 10 per claim, 151 on
`outdoor_time_myopia`. Rendering those distinctively gives a hairball. A citation
is not a rebuttal; papers cite what they build on regardless of agreement.

**Use instead:** match on shared `population` + `exposure` + `outcome` (and,
on timeline claims, overlapping age windows) with opposite stances — a join over
columns the screen pass already fills, so no extra inference. Restrict to the
top-importance slice.

**The weak point is fuzzy matching on the free-text `outcome`.** A controlled
vocabulary per claim would fix it, and is probably over-engineering until the join has
been tried as-is.

**Ruled out on cost:** pairwise LLM comparison of every paper against every other.
150 papers is ~11,000 calls *per claim* — three orders of magnitude past the budget
for the whole corpus.

Build it so that **zero links is a normal, unremarkable state.** If it fires
constantly, that is evidence the relevance tiering is not working, and the link
view has become a debugging tool for the taxonomy.

**Blocked by:** 1. Half the "conflicts" drawn today would be a correct paper
linked to a misclassified one.

---

## P3 — New capability.

### 8. Age timeline for non-binary questions

**Keep the claim binary; put age on the evidence view's X axis.** If the claim
becomes a question ("what is the best age for cow's milk"), no paper can support
or refute it and Y goes undefined — the one axis the reader has learned. The
claim stays *"Cow's milk should not be given as a main drink before 12 months"*,
and age becomes a third mode on the X switch that already toggles design
strength / year.

**Papers are segments, not points.** LEAP randomised at 4–11 months. Plot a
horizontal bar spanning the window with weight spread across it; a dot at 7.5
asserts a precision the abstract does not have.

**The payoff is the crossover, not the clustering.** With `age_min_months` on
every paper, compute the age at which weighted stance flips from refute to
support, and draw two vertical lines — where the claim puts the threshold, and
where the evidence puts it:

> The claim says 12 months. The evidence crosses at 9.4.

**Per-claim opt-in, chosen by semantics first and null rate second.** 27 of 80
claims mention timing, but only ~13 are genuine *threshold* questions where a
crossover means anything: `peanut_intro_early`, `peanut_intro_delay_risk`,
`egg_intro_early`, `weaning_6m`, `weaning_before_4m_risk`, `cow_milk_12m`,
`juice_limit`, `honey_avoid_12m`, `sugar_limit`, `no_screens_under_2`,
`texture_window`, `iron_rich_6m`, `allergen_variety_early`.

Sparsity is the real risk. A regex proxy for age phrases in abstracts (a ceiling,
since it over-counts follow-up windows):

| Claim | Abstracts | Contain an age phrase |
|---|---|---|
| `cow_milk_12m` | 61 | 69% |
| `no_screens_under_2` | 131 | 56% |
| `cow_milk_anaemia` | 72 | 47% |
| `peanut_intro_early` | 157 | 46% |
| `honey_avoid_12m` | 183 | 22% |

`honey_avoid_12m` at 22% would give a near-empty timeline — but that claim is not
a timing question anyway, it is "does this hurt". Do not let its null rate argue
against the axis.

**Cheapest go/no-go in the whole backlog:** run the screen prompt over
`cow_milk_12m` alone (61 pairs, minutes) and read the real null rate before
committing to any timeline UI.

Registry gains `age_axis: True`, `threshold_months: int`. `claim_papers` gains
the age columns listed at the foot of `prompts_v2.py` — per-pair, because the
same paper is direct evidence for one claim and background for another.

**Blocked by:** 1 (the age fields come out of the screen pass).

---

### 9. Cross-claim contradiction detection

`peanut_intro_early` ("before 6 months") and `peanut_intro_delay_risk` ("beyond
12 months") are the same question asked at two thresholds, judged independently.
On an age axis they should produce the **same** evidence crossover from the same
literature. If they do not, that is a real finding about the map.

This is SPEC §9's open question — "claims are judged independently, so the map
cannot yet notice when two of its own claims disagree" — and the age axis is the
first tool that could detect it.

**Blocked by:** 8.

---

## Decided and closed — do not re-litigate

| Question | Decision | Because |
|---|---|---|
| Citation edges as a contested-link proxy | **Rejected** | 16% of all edges connect opposite stances. Hairball, not signal. |
| Bolt a polarity-flip field onto the existing stance ladder | **Rejected** | Would break 9 correct rows to fix 9 wrong ones on `back_to_sleep`. The existing `direction` field already compensates half the time. |
| Reword the 12 protective claims' `tested_as` instead of fixing the prompt | **Rejected as a standalone fix** | Mirrors the inversion rather than removing it, cannot touch outcome-polarity cases (ferritin vs anaemia), does not generalise to claim 81 — and still costs a full re-run, so it is not the cheap option it looks like. |
| Push contested claims leftward on X | **Rejected** | Collapses "unstudied" and "genuinely disputed" onto one coordinate. Whisker instead (item 6). |
| Cut framework / context papers entirely | **Rejected** | Method provenance is what makes a body of evidence persuasive rather than dismissible. Kept, re-rendered (item 4). |
| Keep the conservative/balanced/liberal toggle as a control | **Rejected** | 2.5% of pairs are `mixed`. Stated as a number on the claim instead (item 3). |
| A recency term in the reading-order rank | **Rejected** | Asserts newer is better, which is false. The measured age skew is the citation term counting elapsed time — fix it there ([D24](DECISIONS.md#d24), item 15). |
| Remove the size/rank redundancy on paper cards | **Rejected** | Same quantity in a coarse channel and a precise one: find by eye, confirm by number. The gap was the missing explanation, now on the open card ([D23](DECISIONS.md#d23)). |

---

## Found while explaining the ranking (2026-08-30)

Out of putting the `importance_of` arithmetic on the open card
([D23](DECISIONS.md#d23)). Item 14 is the one with a deadline: it is nearly free
now and expensive later.

### 14. Sample size is not extracted, and this is the only cheap moment to add it

[D16](DECISIONS.md#d16) took sample size out of the quality signal because the
model's `evidence_strength` label *conflated* it with design — "strong =
meta-analysis or large RCT" — not because size does not matter. The consequence
stands today: an n=30 RCT and an n=3,000 RCT are both `designRank` 0.88 and
differ in the ranking only by however many citations each happened to collect.

Extracted as its own field, `n` does not contaminate the design ladder and gives
the rank a quality term that is about the study rather than about its reception.

**The timing is the point.** This needs a value on every pair, so it needs a full
pass — 14-25 hours. One is already planned (item 1f) and `prompts_v2.py` is
being drafted now. Added to the draft it costs a few tokens per pair; added after
the re-run it costs another re-run. Exactly the argument already made at the foot
of `prompts_v2.py` for the age window.

**Blocked by:** nothing, and it blocks 1f. Do it while the prompts are open.

---

### 15. The citation term counts elapsed time, so recent work sinks

Median rank percentile by year: flat at ~0.44 through 2021, then 0.67 (2024),
0.73 (2025), 0.83 (2026). A 2025 paper is in the bottom third of its claim by
construction. Full measurement and the reasoning for fixing it *here* rather
than with a recency term is [D24](DECISIONS.md#d24).

Two candidates: age-normalise citations (percentile within publication year, or
citations per year), or blend the journal metric in as a prior for papers under
~2 years old, decaying as citations arrive — the one use of that metric
[D15](DECISIONS.md#d15) did not reject.

**Blocked by:** 16. Changing the citation term and the weights separately means
measuring the same thing twice.

---

### 16. The importance weights have never been calibrated against anything

`0.45 / 0.35 / 0.20` appear in `DECISIONS.md` only in passing, inside
[D15](DECISIONS.md#d15)'s description of what the journal term does. They have
been rendering as a result for weeks. They are now named
(`W_DESIGN` / `W_CITATIONS` / `W_JOURNAL`) and printed on the open card, which
makes the gap visible but does not close it.

What would close it: a reading-order question put to the gold set's 60 pairs —
*"which of these two should a parent read first?"* — and the weights fitted to
the answers. That is a second labelling pass over pairs already in hand, not a
new corpus.

Two things worth measuring at the same time:

- **The journal term is nearly inert.** It is the largest of the three terms on
  2% of papers. It may be doing its work as a tie-breaker rather than a driver —
  its median rank-correlation with the final order is +0.48 — or it may be
  buying very little for the bias [D15](DECISIONS.md#d15) documents.
- **The design ladder's lumpiness.** Twenty rungs, most papers on a handful of
  them, so the 0.45 term ties far more often than its weight suggests and the
  0.35 citation term does more of the ordering. Whether that is a weighting
  problem or a laddering problem is measurable and currently unmeasured.

**Blocked by:** nothing, but it wants the gold set extended.

---

### 17. Where relevance enters the arithmetic is undecided

The screen pass ([D22](DECISIONS.md#d22)) will produce a relevance tier and a
`relevance_reason` — population, outcome, dose, route, model organism. Item 3
already plans per-reason discounts. What is not decided is *which* number they
discount.

**A fourth additive term is the wrong shape.** In a sum, a large weight rescues
a bad relevance: an off-population meta-analysis in a strong journal keeps
0.45 + 0.20 before relevance is even consulted, and still outranks a
well-matched cohort. Relevance is closer to a gate or a multiplier —
`importance x relevance_factor`, 1.0 for direct — than to an addend.

It is also two questions, not one: whether relevance discounts the **verdict
weight** (`paper_weight`, which moves the claim) or the **reading-order rank**
(`importance_of`, which orders the cards), or both by different amounts. They
are deliberately separate today ([D15](DECISIONS.md#d15)) and should stay so.

**Partly settled by [D25](DECISIONS.md#d25).** The gate is decided: `netSupport`
draws only from `stance` on `direct` and `indirect`, and `stated_position` never
enters it. What remains open is the *graded* question inside that gate — whether
`indirect` is discounted relative to `direct`, by how much, and whether the same
factor applies to `importance_of` (reading order) as to `paper_weight` (verdict
weight). D15 keeps those two separate and D25 does not change that.

**Blocked by:** 1e. There is nothing to discount until the screen pass fills the
enum.

---

### 18. Context papers carry a rank they are never shown

`rank_papers` ranks every paper held for the claim, neutrals included, and the
rank travels into the JSON. But a context paper is drawn outside the plot with
no X or Y, so its rank describes a position it was never given. The open card
therefore shows the importance breakdown on decisive papers only, which is
correct on screen and leaves the data model saying something the UI has to
suppress.

Either stop ranking neutrals, or rank them separately as "background worth
reading". Small, and only worth doing when the screen pass changes what
`neutral` means anyway (item 1e).

---

### 19. Claim lifecycle — add, re-run, amend, retire

`CLAIMS` in `backend/claims.py` is a hand-edited literal, and editing it is only
the first step. A new or changed claim then needs `import_claims.py` to collect
for it, `evaluate_claims.py` to judge it, and `build_claims_data.py` to export
it. Nothing sequences that, so every claim operation is a multi-command ritual
that has to be remembered correctly — and a half-finished one leaves a claim on
the map with zero papers and no signal that it is unfinished rather than
unstudied, which is the one thing the map must never get wrong.

It became blocking twice on 2026-08-31: `responsive_interaction` and
`motor_cognitive_link` were dropped for being unfalsifiable
(`gold/dropped_claims.md`), and the audit pass rewrote a further batch. Both
wanted a re-run of one claim; neither had a path to it.

**Four operations, one mechanism:**

| | does |
|---|---|
| **add** | new key, collect, evaluate, export |
| **re-run** | same key, re-collect and/or re-evaluate — after a wording change, a new model, or a new prompt |
| **amend** | change wording, sign or type. Invalidates every stored verdict for that claim, because they were judged against the old sentence. Must say so and offer the re-run. |
| **retire** | leave the map. Papers stay in claims.db; only the registry entry goes. |

**Amend is the dangerous one.** Rewriting `bilingual_no_delay` from a negation to
a positive assertion inverts the meaning of all 118 stored verdicts on it. There
is currently nothing that notices, so the exported JSON would keep serving them
against the new wording. Any amend path has to mark the claim stale and refuse
to export it until re-evaluated.

**A row of the audit table is the input.** `gold/claim_audit.csv` already holds
exactly what a claim needs: the two wordings, `claim_type`, `claim_sign`,
exposure, outcome, age range, the OpenAlex query, keyword hints, the stakes
fields and the guidance links. So the mechanism is "take one row, make it real",
and the registry stops being a Python literal edited by hand.

**Wanted, in order:**

1. `python backend/claim.py add|rerun|amend|retire <key>` — resumable, honest
   about which stage a claim has reached, and refusing to export a stale one.
   `--counts-only` already proves the cheap-sizing step works.
2. A claim-state column so the UI can distinguish *no papers collected yet* from
   *collected and nobody has studied it* — currently indistinguishable, and they
   mean opposite things to a reader.
3. Only then, a **form on the site** that writes a row and triggers the pipeline.
   The form is the easy part; it is worth nothing until the four operations
   above are safe to run unattended.

**Note:** retiring a claim orphans its `claim_papers` rows rather than deleting
them. That is deliberate — the OpenAlex spend is not recoverable — but it means
DB row counts drift above the registry and nothing says so.

---

### 20. Measured on 2026-08-31, against the full corpus

Numbers used above were estimates. Re-measured over all 6,672 abstracts in
`claims.db`:

| | count | share |
|---|---|---|
| longer than the 1,800-char prompt cut | 2,295 | **34.4%** |
| ...whose CONCLUSIONS section falls past the cut | 437 | **6.5%** |
| ends mid-sentence (no terminal punctuation) | 250 | 3.7% |
| copyright / licence boilerplate in the text | 33 | 0.5% |
| very short (< 200 chars) | 30 | 0.4% |
| reference-link markup leaking into the text | 1 | 0.0% |

A third of abstracts are cut at all; 437 papers have their finding severed
before the model ever reads it. That is the one worth fixing — raising the cut
costs context window, but a conclusion-aware truncation (keep the head and the
CONCLUSIONS block, drop the methods in between) costs nothing.

**But it is not what is driving the contested gold rows.** Across controversy
bands the truncation rate runs 33% / 36% / 47% / 22% — no pattern. Real problem,
wrong suspect for the current disagreements.

The reference-markup case is a single paper (`n=16` in the gold set, a BMJ
Evidence-Based Nursing abstract ending in `[3]: /lookup/external-ref?...`). Worth
a two-line strip in `openalex.py`, not worth a project.

---

### 21. `bakeoff.py`'s `decomposed` is 1e, not 1c

Named on the assumption they were the same thing. They are not, and the
distinction matters:

- **1e** — the screen/stance split ([D22](DECISIONS.md#d22), now
  [D25](DECISIONS.md#d25)). Asks *does this paper bear on the claim?* This is
  what is wired in and measured.
- **1c** — the polarity decomposition. Model reports `effect`,
  `exposure_polarity`, `outcome_polarity`; stance is computed **in Python**
  against a per-claim `claim_sign`. Asks *which way does it point?* **Unbuilt.**

Only 1c addresses the complement-exposure failure, because it takes the logical
flip away from the model entirely. This is why the `complement` stratum did not
move when the two-call screen was measured: 43% under one call, 43% under two.
Nothing in 1e was ever aimed at it.

Rename the registry entry to `screened` when 1c lands, so the two can be
measured side by side without the names colliding.

---

### 22. The hardware assumption in 1b is wrong for the Windows machine

1b reads "Hardware caps local at ~20B (16 GB GPU) or ~27B (24 GB Mac)". The
Windows laptop has an **RTX 4050 with 6 GB of VRAM**, not 16. Measured there:

- `qwen3:8b` (5.2 GB) is the largest model that fits fully on the card
- Ollama's own fit estimator leaves ~2 GB unused and spills 25% of layers to
  CPU, which drops throughput from 35 tok/s to 15.6 — pinned via
  `backend/Modelfile.qwen3-8b-gpu` plus `OLLAMA_FLASH_ATTENTION=1` and
  `OLLAMA_KV_CACHE_TYPE=q8_0`
- a full 7,769-pair pass measures **32.6 h** one-call, **74.1 h** two-call

`gpt-oss:20b` needs ~13 GB and would run mostly in system RAM on a machine with
15.7 GB total. It is not reachable here, so bake-off cells 2-4 as written in
`gold/README.md` need rethinking rather than running.

---

### 23. The re-run may have swapped one distortion for its mirror image

Observed 35% into the 2026-09-02 pass (qwen3:8b, `current` prompt, 1,353 pairs
re-judged). Against the same pairs' mistral verdicts:

| | mistral | qwen3 |
|---|---|---|
| supports | 681 | 389 |
| refutes | **313** | **37** |
| neutral | 325 | 908 |
| mixed | 34 | 19 |

Refutes fell 88%. Of 19 claims with five or more directional verdicts, **none**
read as refuted and none as contested: 11 sit between +0.50 and +0.99, and 8
have no refuting paper at all.

The direction is what item 1 asked for — `honey_avoid_12m` moves from -0.01 to
+0.92 and `back_to_sleep` from +0.23 to +1.00, and those are settled facts the
map was reading as contested. But item 1 predicted +0.20 for `back_to_sleep`,
not +1.00, and **a map that cannot refute anything is as uninformative as one
that contests everything.** It also cannot do the thing the reader most needs:
say that a widely-believed claim is not supported.

Three explanations, not yet separable:

1. **It is correct.** These particular claims are well-supported and the old
   contested reading was inversion error. The gold set is consistent with this:
   qwen3 scored 75% on the `refutes` stratum, so it demonstrably can say refutes.
2. **The model is refutes-averse — now the leading explanation.** 37 refutes in
   1,353 pairs is a strong prior on its own. What settles it is the Mac's
   bake-off of `gpt-oss:20b`, run the same day: a larger and more careful model
   answered **`neutral` on 47 of 57 gold pairs**, reaching "does not test it"
   through real reasoning about a real extracted finding. It scored 46% overall
   and 29% on complement — below the mistral pass it would have replaced —
   purely by declining to take a position.

   So neutral-aversion is not a qwen3 quirk; it is what a careful judge does on
   this task, and qwen3 is a milder case of the same thing. That reframes the
   908 neutrals: some fraction is correct relevance filtering, and some is a
   judge that will not commit. The two are not currently separable, and nothing
   in the pipeline distinguishes "this paper does not test the claim" from "I
   would rather not say" — which is precisely the distinction D25's `relevance`
   tier was designed to make.

   The gold set holds only ~5 scoreable `refutes` rows, far too few to have
   caught a bias this size. That is a gap in the gold set as much as a question
   about the model.
3. **Selection.** Rows are processed best-first by keyword score, so the
   best-matched papers are judged first and may skew supportive. The contested
   claims may simply not be done yet.

**The cleanest test is already set up.** `bilingual_no_delay` and
`crawling_not_required` were rewritten from negations into positive assertions
specifically so the evidence could refute them. Both are in the Mac shard. If
neither comes back refuted, explanation 1 is dead.

**Do not export or ship until this is resolved.** `build_claims_data.py` has not
been run, so nothing is live; keep it that way until the shards finish and those
two claims are read.

**Follow-on for the gold set:** it needs more genuinely-refuted rows. Five is not
enough to detect a model that never says no, and that is exactly the failure this
pass may have introduced.

### 23a. Largely resolved — it was selection, not aversion

Re-read on 2026-09-02 evening with both shards merged, 2,548 pairs judged
(windows 1,466, mac 1,080). The alarming reading was an artefact of how few
claims had got far enough, exactly as explanation 3 proposed.

| | yesterday, 19 claims | now, 43 claims |
|---|---|---|
| net **negative** (refuted) | 0 | **2** |
| 0 to +0.49 (contested) | 0 | **4** |
| +0.50 to +0.99 | 11 | 21 |
| +1.00 (no refutes at all) | 8 | 16 |

- `blw_choking` sits at **-1.00** — 0 supports, 6 refutes. The map can refute.
- `bilingual_no_delay` sits at **-0.60**. That is the claim rewritten from a
  negation into a positive assertion *specifically so evidence could refute it*,
  and it is being refuted. The designed test passes.

Rows are processed best-first by keyword score, so the earliest-finished claims
are the ones whose best-matched papers agree with them. Reading a refutes rate
off a third of a pass measures the ordering, not the model.

**What is still true and still worth watching:** the corpus-wide refutes rate is
2.7% against mistral's 20.2%, and neutral has gone from 31% to 68%. Much of that
drop is correct — on the gold set mistral gave hard verdicts to 22 of 32
off-topic papers and qwen3 to 2, and those now land in `neutral`, which
netSupport already excludes. But "correctly declined" and "would rather not say"
are still indistinguishable in the data, which is D25's relevance tier again.

**The export is no longer blocked on this.** Finish both shards, re-read the
distribution above, then run `build_claims_data.py`.

**First data on the test, from the Mac shard (paused at 1,080/3,784).**
`bilingual_no_delay` is 14/118 judged, and those 14 are **4 refutes, 3 mixed,
1 supports, 6 neutral**. A 29% refutes rate on the claim written to be refutable,
against 2.8% (30/1,080) across the shard as a whole — an order of magnitude
apart, on the claim where the difference was predicted.

That is early and small, but it points away from explanation 2: a model that
cannot say no does not say it ten times more often on precisely the claim the
evidence should refute. Explanation 3 gains from the same fact — if best-first
selection is what suppresses refutes elsewhere, a claim whose best-matched
papers genuinely refute it is exactly where refutes would surface first.

`crawling_not_required` is 0/10 and has nothing to say yet. Both need their
remaining rows before this is settled; the shard-wide refutes rate is the number
to re-read when it finishes, not this one.

---

## Found while labelling the gold set (2026-08-29)

These came out of hand-labelling and are not in the sections above. Both are
P0-adjacent: they are about the model not receiving what it needs, which is
upstream of any prompt or model choice.

### 10. Abstracts are truncated at 1,800 characters, and 6.5% lose their conclusion

`evaluate_claims.py` cuts every abstract at 1,800 characters before the model
sees it. Measured over the corpus:

| | pairs | share |
|---|---|---|
| have an abstract | 7,769 | |
| truncated at 1,800 | 2,730 | 35.1% |
| losing 600+ characters | 836 | 10.8% |
| **CONCLUSION section cut off entirely** | **675** | **8.7%** |

So on roughly one pair in twelve the model is asked what a paper concluded
while the authors' own statement of what they concluded has been removed from
the input. Structured abstracts put CONCLUSION last, so truncation removes
exactly the most load-bearing sentence.

The limit is a leftover, not a constraint — 1,800 characters is ~450 tokens
against context windows measured in tens of thousands. Raising it to cover the
99th percentile costs a little inference time per pair and nothing else.

**Do this before the re-run**, and before drawing any conclusion about which
model or prompt is better: some share of the current error rate is a model
judging a paper it was not allowed to finish reading.

### 12. The claim anchor no longer sits at the centre of its papers, and does not say so

`DECISIONS.md` [D20] moved a claim's X from the mean of its papers' design ranks
to a top-weighted aggregate, deliberately: the mean reported the state of the
literature rather than the state of the answer, and left every claim in the
left-hand half of the axis.

The consequence is on screen and unexplained. The evidence view pins the claim
above its cloud of papers, and that anchor now sits **right of the median paper
on all 77 claims** with enough papers to judge — worst gap 0.435. A reader who
notices reads it as an inconsistency, because nothing tells them the claim is
positioned by its *best* evidence while the dots are positioned individually.

SPEC §3.3 currently says the claim "appears as a circle pinned at the coordinates
it occupied one level up" so the reader can see "when a handful of heavily-cited
studies have pulled that verdict away from where the bulk of the papers sit".
That sentence now describes something the reader cannot check, since the pull is
by construction rather than by evidence.

Fix is wording, not geometry: say on the evidence view that the claim sits with
its strongest studies. Blocked on nothing.

---

### 11. Some claims are not comprehensible to a reader

Found on gold-set row #7:

> *"Responsive serve-and-return interaction supports infant brain development"*

The labeller — who wrote the claim registry — could not tell what it was
asserting. If the author cannot parse it, a parent searching for it cannot, and
neither can a 7B model. This is a claim-wording bug rather than an evaluation
bug, and it is invisible from inside the pipeline because the model always
returns *something*.

Worth a pass over all 80 claims asking only: would a parent recognise this
sentence as something they have been told? SPEC §9 already flags claim curation
as open; this is a concrete instance of it.

Related, from row #9: a paper can **presuppose** the claim rather than test it —
a prevalence survey reporting breastfeeding *rates* assumes the benefit instead
of measuring it. That is a distinct kind of non-evidence, it is probably common,
and a model will otherwise read topic-match plus positive framing as support. It
deserves an explicit `background` example in the screen prompt.

---

## Found before the restructure (2026-08-23)

Both are data-integrity items rather than design work, and both are invisible
from the map: the pipeline reports success in each case. See `DECISIONS.md`
D15–D17 for the decisions from the same period.

### 12. Retraction status is unverified for 62% of the corpus, and looks solved

The filtering is correct and in place — [`evaluate_claims.py:189`](backend/evaluate_claims.py#L189)
and [`build_claims_data.py:85`](backend/build_claims_data.py#L85) both exclude
`is_retracted`. That is exactly what makes this dangerous: it reads as done.

`is_retracted` was only added to the OpenAlex `select` in time for the final
30-claim import, and that import ran `--skip-done`, so the 50 claims already
held were never re-fetched.

| | papers |
|---|---|
| fetched with `is_retracted` in the select | 2,536 |
| **never actually checked** | **4,136 (62%)** |
| corpus total | 6,672 |

Those 4,136 hold the column default of `0`, which is **unverified**, not
verified-false — and nothing distinguishes the two. One retracted paper has been
caught so far, a Cochrane review cited 1,528 times, which is the argument for
checking the rest rather than against it.

**Fix.** Re-fetch retraction status for the unchecked papers. OpenAlex accepts
pipe-separated OR filters on ids, 100 per request, so 4,136 papers is ~42
requests — well inside one day's free budget, and independent of everything else
in this file. Consider storing a `retraction_checked_at` timestamp so "not
retracted" and "not looked at" stop being the same value.

Adding fields to the `select` is free: OpenAlex bills a flat rate per request
regardless of what comes back (SPEC §6). There is no reason for any future import
to omit a field it might want.

### 13. `mixed` is contaminated — roughly half are not two-sided papers

[D9](DECISIONS.md#d9) retires the readings toggle because `mixed` is only 2.5% of
pairs. Correct, but it leaves the category itself unexamined, and the plan that
replaces the toggle — stating the conservative/liberal spread **on the claim** —
is computed from these same weights.

Sampling the `mixed` verdicts, about half are papers that do not test the claim
at all, and their own stored `finding` says so:

> `vit_d_supplement` — *"does not directly address breastfed infants requiring
> supplementation"*
> `heavy_metals_rice` — *"does not specifically conclude whether levels are
> concerning"*

Those are `neutral`. The prompt asks for "both ways", and the model appears to
reach for `mixed` when it means "neither".

**This is findable by query rather than by re-running inference**, because the
reasoning is stored: `stance = 'mixed'` where `finding` matches *does not
address / does not test / not specifically*. `backend/audit_stances.py` already
does the general version of this — and note its design, which is reusable: it
classifies the stored summary **without showing the model the stored stance**,
then compares. Asking "do you agree with this verdict?" invites agreement; asking
cold and comparing does not.

Cheap, and it should happen before any spread number is put on a claim. If the
re-run under a new prompt ([D5](DECISIONS.md#d5)) lands first, re-measure rather
than assuming the contamination survived — the decomposed prompt has no `mixed`
escape hatch in the same shape.
