# Decisions

A record of what was found, what was chosen, and why. **Append only.** An entry
is never deleted when the work it describes is finished — the reasoning is the
point, and the most expensive mistake in this project would be re-proposing
something that was already measured and ruled out.

Append-only applies to the *substance*. An entry may gain a dated **Superseded**
or **Amended** block when a later decision overturns part of it — added below
what it revises, never replacing it, and linked both ways so neither can be read
without the other (see [D16](#d16) and [D20](#d20)). What is never done is
editing an entry so it appears to have said something else all along.

**IDs are permanent and are not renumbered**, so they can be cited from code,
commits and `SPEC.md`. The index below is ordered by date; the numbers are not
chronological, because entries were written up in a different order from the one
they were decided in.

Companions: `SPEC.md` says what the project is for and the rules it holds itself
to. `BACKLOG.md` says what to do next and shrinks as work completes. This file
says why, and only grows.

**Entry format.** A heading names the *area* a decision was taken in, never the
position taken — because positions get overturned and the area does not, and an
entry titled with a conclusion that no longer holds is a trap for whoever reads
it next. Where it stands today is the index column and the body. Each entry
carries the evidence and — where it applies — *what would change our mind*. A
decision without that last field is dogma rather than a decision.

---

## Index

| # | Date | Area | Where it stands | Status |
|---|---|---|---|---|
| [D15](#d15) | 2026-08-23 | What the journal a paper appeared in is worth | Nothing to the verdict; 20% of the reading-order rank | rejected |
| [D16](#d16) | 2026-08-23 | What ranks an individual paper's quality | A normalised design ladder, not the model's strength label | decided |
| [D17](#d17) | 2026-08-23 | Whether a full pass can be made faster | Not by parallelism — local inference is memory-bandwidth bound | finding |
| [D18](#d18) | 2026-08-24 | How verdicts are lost between the model and the database | A brace-matching parser was discarding the model's hedged answers | finding |
| [D19](#d19) | 2026-08-25 | Whether colour can carry meaning legibly | Not as drawn — the stance palette fails AA at every point | decided |
| [D20](#d20) | 2026-08-26 | How a claim's position aggregates its papers' | Weighted to the best quarter and tenth, not the mean — supersedes part of [D16](#d16) | decided |
| [D1](#d1) | 2026-08-29 | Whether the verdicts are sound enough to build on | Not yet — settled claims read as contested | finding |
| [D2](#d2) | 2026-08-29 | How the misclassification breaks down | Two distinct modes: polarity inversion and relevance leakage | finding |
| [D3](#d3) | 2026-08-29 | Fixing inversion by patching the stance ladder | Rejected — the step is right 50% of the time, so there is no rule to patch | rejected |
| [D4](#d4) | 2026-08-29 | Fixing inversion by rewording the claims | Rejected as a standalone fix — mirrors the inversion, costs the same re-run | rejected |
| [D5](#d5) | 2026-08-29 | How the stance question is put to the model | Decompose into three readable facts; compose the verdict in Python | proposed |
| [D6](#d6) | 2026-08-29 | How a prompt or model change is measured | A 60-pair gold set, built before any full re-run | decided |
| [D7](#d7) | 2026-08-29 | Where inference runs, and what that leaves us | Local; the ~20B ceiling makes prompt structure the only lever | decided |
| [D8](#d8) | 2026-08-29 | How disagreement between papers is detected | Not from citation edges — 16% of them join opposite stances | rejected |
| [D9](#d9) | 2026-08-29 | How two-sided papers are handled on screen | Ship `balanced` alone; state the spread as a number | decided |
| [D10](#d10) | 2026-08-29 | Whether framework papers belong on the map | Kept, re-rendered as "how this question is tested" | decided |
| [D11](#d11) | 2026-08-29 | How contestedness is shown | A leftward whisker from the true X, not a moved dot | decided |
| [D12](#d12) | 2026-08-29 | How questions about timing are handled | Claims stay binary; age becomes a third mode on the X switch | decided |
| [D13](#d13) | 2026-08-29 | How much of an abstract the model receives | 1,800 characters — 8.7% of pairs lose their conclusion outright | finding |
| [D14](#d14) | 2026-08-29 | How a paper's influence on its claim is expressed | A leave-one-out delta, not a share of a total | decided |
| [D21](#d21) | 2026-08-29 | What makes a paper evidence for a claim | Four tiers, judged on what was measured — never on whether it agrees | decided |
| [D22](#d22) | 2026-08-29 | How the relevance and stance questions are put | Two calls; the cheap screen gates the expensive judgement | decided |
| [D23](#d23) | 2026-08-30 | What a paper card shows, and what the map encodes twice | Rank stays the headline; the open card shows the arithmetic behind it | decided |
| [D24](#d24) | 2026-08-30 | Whether a paper's age should affect its rank | No recency term — the age skew is the citation term measuring elapsed time | decided |

---

<a id="d1"></a>
## D1 — Whether the verdicts are sound enough to build on
**2026-08-29 · finding**

Net support among each claim's *best* papers (top quartile by design × citations):

| Claim | net (all papers) | net (best papers) |
|---|---|---|
| `back_to_sleep` | +0.21 | **−0.02** |
| `vitamin_k_birth` | +0.03 | **−0.04** |
| `salt_limit` | +0.24 | **−0.02** |
| `honey_avoid_12m` | −0.05 | **−0.20** |

Back-to-sleep and vitamin K at birth are among the most settled facts in
paediatrics. The map reads them as open questions.

**Consequence.** Every display feature that depends on the verdict — contested
flagging, opposing-paper links, per-card influence — would ship as a renderer
for classification errors. Correctness is therefore ordered ahead of all of
them, and this is the reason.

---

<a id="d2"></a>
## D2 — How the misclassification breaks down
**2026-08-29 · finding**

Reading the top "refuting" papers on `back_to_sleep` separates them cleanly.

**Polarity inversion.** The model writes a correct finding and then flips the
direction:

> *"Prone and side sleeping positions increase the risk of SIDS compared to
> supine"* → stored as **refutes** the claim that back sleeping reduces SIDS.

It matched on the word "increase". ~13% of refutes-rows across the 12
protective-framing claims assert an *increased* risk in their own stored finding
text. Correcting the 9 mechanically-detectable cases on `back_to_sleep` moves it
from −0.02 to **+0.20** among its best papers.

**Relevance leakage.** Papers on serotonergic receptor binding, sudden death in
epilepsy, and bed-sharing are all scored `refutes` on a sleep-position claim.
They do not test it at all.

**Which dominates is not yet settled.** Early gold-set labelling put 6 of the
first 8 human/model disagreements in relevance rather than stance — but that
sample is deliberately loaded with suspicious rows, so the *rate* does not
generalise. The ratio is what the gold set is for ([D6](#d6)).

**Why it matters that they are separate:** the two-call screen/stance split fixes
leakage and does nothing for polarity. They need different fixes.

---

<a id="d3"></a>
## D3 — Fixing inversion by patching the stance ladder
**2026-08-29 · rejected**

The tempting minimal fix: keep `finding → direction → stance`, add an
`exposure_polarity` field, flip the direction when it says "opposite".

**Measured on `back_to_sleep`**, over every stored finding that reports the
complement exposure ("prone increases risk" rather than "supine reduces risk"):

```
already scored supports (model handled the flip)   9
scored refutes (model inverted)                    9
```

Exactly half. An unconditional flip would break 9 correct rows to fix 9 wrong
ones — net zero, plus a new field.

**The deeper reading:** a step that is right 50% of the time is not a rule being
applied badly, it is no rule at all. The model is pattern-matching on surface
polarity. A coin cannot be patched; it has to be replaced with arithmetic.

---

<a id="d4"></a>
## D4 — Fixing inversion by rewording the claims
**2026-08-29 · rejected**

The alternative minimal fix: change `tested_as` on the 12 protective claims so
the exposure matches how the literature reports it.

> now: *"Placing infants on their back to sleep reduces the risk of SIDS"*
> new: *"Prone or side sleeping increases the risk of SIDS compared with supine"*

Genuinely appealing — most SIDS papers do report prone as the risk factor.
Rejected on four counts:

1. **It mirrors the inversion rather than removing it.** A paper that reports
   "supine is protective" becomes the complement instead, and inverts the other
   way. The 50/50 moves; it does not go away.
2. **It cannot reach outcome-polarity cases.** `cow_milk_anaemia` claims cow's
   milk *increases* anaemia; a paper finds it *lowers ferritin*. Same finding,
   opposite words. No rewording of the claim touches that.
3. **It does not generalise.** Twelve hand-fixes; claim 81 reintroduces the bug.
4. **It is not the cheap option it looks like.** Changing `tested_as` changes what
   the model sees, so it costs a full re-run exactly like the other candidates.

That fourth point is what settles it. **Every option costs the same pass**, so
there is no reason to buy the timid one.

Rewording individual claims remains fine where the wording is genuinely poor —
see [D6](#d6) and the claim-comprehensibility finding in `BACKLOG.md` §11.

---

<a id="d5"></a>
## D5 — How the stance question is put to the model
**2026-08-29 · proposed, pending measurement**

Stop asking the model whether a paper agrees with the claim — a four-step
composition (parse the paper's causal direction, parse the claim's, notice
whether the exposures are complements, compose) with a negation in the middle.
Ask instead for three facts readable straight off the abstract:

```
effect             does the paper's exposure make its outcome MORE or LESS likely?
exposure_polarity  the claim's exposure, or its opposite?
outcome_polarity   the claim's outcome, or its opposite?

sign   = EFFECT[effect] × POL[exposure_polarity] × POL[outcome_polarity]
stance = "supports" if sign == claim_sign else "refutes"
```

| Paper | effect | exp | out | product | claim | → |
|---|---|---|---|---|---|---|
| "Prone increases SIDS risk" | +1 | opposite | same | −1 | −1 | supports |
| "Supine reduces SIDS risk" | −1 | same | same | −1 | −1 | supports |
| "Cow's milk lowers ferritin" | −1 | same | opposite | +1 | +1 | supports |

Both phrasings of the SIDS finding land in the same place. **The verdict stops
depending on which direction an author chose to write their sentence.**

**On the black-box objection** — that this puts more machinery between the reader
and the verdict. It does the opposite. The flip is happening either way; today
it happens inside a token stream that no longer exists, which is why the card
can show `AGAINST` above a sentence that plainly supports and no reader can tell
which half is wrong. Decomposed, the stored fields assemble into a sentence a
parent can check:

> *This paper found that prone sleeping increases SIDS risk. Prone is the
> opposite of back sleeping — so this supports the claim.*

And when the model gets `exposure_polarity` wrong, that sentence reads as
nonsense, visibly, instead of failing silently. This is the same pattern SPEC §5
already applies one level up: do the translation, then show it.

**Costs:** 80 hand-set `claim_sign` values (one wrong sign flips a whole claim,
so they get eyeballed as a printed table), plus `claim_exposure` and
`claim_outcome` in the registry.

**What would change our mind:** the gold set. If a ~20B local model clears the
complement rows on the *current* prompt, this is unnecessary complexity and
should not ship.

---

<a id="d6"></a>
## D6 — How a prompt or model change is measured
**2026-08-29 · decided**

60 hand-labelled pairs across 41 claims, stratified by stance and deliberately
loaded with complement-exposure cases. `gold/`, with `backend/bakeoff.py` to
score candidates against it.

**Why it comes first.** A full pass is 14–25 hours. Without a ruler, "is this
prompt better?" can only be answered by loading the map and forming an
impression — which is exactly the process that produced [D1](#d1) and left it
undetected. With one, the same question is a table:

```
run                       overall   complement
mistral / current            62%          47%
gpt-oss:20b / current        71%          53%
gpt-oss:20b / decomposed     88%          87%
```

Three further reasons it earns its hour:

- **The ruler outlives every run.** The same 60 rows measure the model swap, the
  decomposed prompt, the relevance tiering and the age extraction.
- **The cost asymmetry is stark.** An hour of labelling against 15–25 hours of
  compute and the risk of publishing verdicts that invert settled paediatrics.
- **It is the only human anchor in the system.** Principle 4 requires every
  automated judgement to be auditable; without a gold set the sole justification
  for anything on the map is "the model said so".

**Labelling conventions settled in use:** relevance is categorical
(`direct`/`indirect`/`framework`/`background`), never a high/medium/low degree —
a degree scale invites exactly the topic-similarity error the model makes, and
`framework` is a different *kind* of contribution rather than a weaker one. An
explicit `does not test` is accepted for the stance of an unscored tier, because
a blank is ambiguous with "not labelled yet".

---

<a id="d7"></a>
## D7 — Where inference runs, and what that leaves us
**2026-08-29 · decided**

Measured on the available machines:

| | Ceiling at Q4 | Speed |
|---|---|---|
| M4 Pro, 24 GB unified | `qwen3.6:27b` (~17 GB) | ~20–25 s/pair |
| 16 GB GPU | `gpt-oss:20b`, `phi4:14b` | ~2–4 s/pair |

`mistral` (7B, 2023) measured at **6.7 s/pair**, so a full single-call pass is
14.5 h and the two-call design ~24.5 h.

**A frontier model is not reachable locally.** The ceiling is ~20B. That is a
real jump from a 7B but not obviously enough for composition-with-negation —
which means the model is fixed and **prompt structure is the only lever that can
actually be pulled.** That, rather than elegance, is what justifies [D5](#d5).

**On the hosted alternative.** A full pass is ~30M tokens (~26M in, ~3.3M out) —
roughly £30–40 on a mid-tier hosted model, or ~300× the size of a long working
session. Rejected for now, on three grounds: it is a work account, so it is a
spend conversation rather than a decision; local costs nothing and the abstracts
are public so privacy is not the argument; and a pinned local tag is *more*
reproducible than the floating `mistral:latest` currently in use.

**Important distinction, since it caused confusion:** a Claude Team seat and API
access are separate products with separate billing. A seat is not a token
allowance that can be drawn down for a batch pipeline. The seat's legitimate
role here is *measurement* — labelling, and running the ceiling cell of the
bake-off interactively — not production inference.

---

<a id="d8"></a>
## D8 — How disagreement between papers is detected
**2026-08-29 · rejected**

*(This entry supersedes `RESTRUCTURE.md` §4.4, since deleted.)*

The obvious approach — ask the model to compare every pair of papers — was ruled
out on cost before anything else was considered: 150 papers is ~11,000 calls per
claim, three orders of magnitude past the budget for the entire corpus. What was
proposed instead was the free, high-precision alternative: an edge between two papers of opposite stance means one
read the other and disagreed.

**Measured:** opposite-stance citation edges are **1,942 of 12,318 — 16% of all
edges**, median 10 per claim, 151 on `outdoor_time_myopia`. Rendering those
distinctively produces a hairball, not a signal.

A citation is not a rebuttal. Papers cite what they build on regardless of
whether they agree with it.

**Amended 2026-08-26 — what is *drawn* is a separate question from what is
*detected*.** The evidence view now renders only the edges with one end in the
context box: 9,459 corpus-wide down to 3,381. A paper-to-paper citation says one
author read another and nothing about whether either is right or on topic, which
is the only question this screen answers — and at a hundred papers those edges
are most of the ink. `LayoutEngine.EVIDENCE_EDGE_MODE = "all"` restores them.

Found in passing: **254 of the 9,713 exported edges are self-loops**, a paper
citing itself. They were rendering as degenerate zero-length curves and are now
filtered, but they are in the stored citation data and any future analysis over
that table should expect them.

**Use instead:** match on shared population + exposure + outcome (and, on
timeline claims, overlapping age windows) with opposite stances — a join over
columns the screen pass already fills, restricted to the top-importance slice.
Build it so that **zero links is a normal state**; if it fires constantly, that
is evidence the relevance tiering is not working.

---

<a id="d9"></a>
## D9 — How two-sided papers are handled on screen
**2026-08-29 · decided**

`mixed` is **196 of 7,769 pairs (2.5%)**, and the largest count on any single
claim is 9 of 192 (`vit_d_supplement`). So the most prominent control on screen
moves the picture measurably on a handful of claims and does nothing visible on
the rest.

Ship `balanced` as the only layout. Keep computing all three nets, and where
they diverge by more than ~0.15 **say so on the claim** — *"reads +0.6 to −0.1
depending on how its two-sided papers are counted"*. That is still the SPEC §4
signal; it is stated rather than operated.

The freed control becomes the relevance filter: direct only / direct + indirect /
everything. The two are not substitutes — one asks how a two-sided paper is
counted, the other how close a paper is to the claim — but the first has stopped
earning the most prominent control on the screen.

---

<a id="d10"></a>
## D10 — Whether framework papers belong on the map
**2026-08-29 · decided**

The case for cutting them was real: a parent deciding about peanut at six months
is not served by the paper that standardised the food-challenge protocol.

**The case for keeping them, which won:**

> In some fields there are papers that present ways of measuring things. If you
> reference a paper in a conversation it can be dismissed as a one-off — but if
> you want to change someone's mind, this other context about the field adds
> weight. It is not just what they discovered, it is *how* they discovered it.

That is a persuasion function, and it is stronger than the "is this field
coherent?" orientation argument it replaced. It is squarely inside SPEC §1's
"the link to the sources and the quality of the evidence underneath".

**What was actually wrong** is that today they are selected by *failure* — a
paper lands in the context box for not fitting anywhere else, then wins a
citation contest among the other misfits. Under the restructure a paper enters
only if the screen tiers it `framework` **and** names what it offers (method /
measure / definition / mechanism / guideline) **and** it clears the relative
citation bar.

**Render as a claim-panel section, not as cards.** Grey rectangles parked
outside the plot encode nothing on a screen where position is the entire
language:

> **How this question is tested**
> · Double-blind placebo-controlled food challenge — the diagnostic standard *(Sampson 2012, cited by 34 of these papers)*

Default **on**. Everything tiered `background` is dropped and reported as a
count.

---

<a id="d11"></a>
## D11 — How contestedness is shown
**2026-08-29 · decided**

The request was that a contested claim should be pushed left, away from strong
evidence, because disagreement makes the answer less usable.

**Rejected, because it collapses two opposite situations.** X means study-design
quality. Redefining it as "how much you can rely on the answer" puts *"nobody has
run a good study"* and *"two good studies disagree"* on the same coordinate. For
a parent those are opposite: one says wait, the other says the question is
genuinely open.

Instead the dot stays at its true quality X and grows a horizontal whisker
reaching left to where it *would* sit if disagreement were discounted. The reader
gets both numbers and the gap between them, which is more information than the
moved dot, not less. Fallback if the whisker reads as noise: a split or hatched
dot, before a moved one.

Vertical centring needs no mechanism — `net = (S−R)/(S+R)` already puts a strong
supporter and a strong refuter mid-height.

**Measure contestedness among the good papers only.** `consensus = |netSupport|`
is too crude: fifty weak studies disagreeing is an *unstudied* claim, not a
contested one.

---

<a id="d12"></a>
## D12 — How questions about timing are handled
**2026-08-29 · decided**

For non-binary questions ("what is the best age to start cow's milk"), the trap
is that Y stops meaning anything: if the claim is a question rather than a
proposition, no paper can support or refute it, and the one axis the reader has
learned goes undefined.

So the claim stays a threshold — *"Cow's milk should not be given as a main drink
before 12 months"* — and **age becomes a third mode on the X switch** that
already toggles design strength and year. A small change to machinery that
exists, rather than a new level.

Three things that follow:

- **Papers are segments, not points.** LEAP randomised at 4–11 months. Plot a bar
  across the window with weight spread over it; a dot at 7.5 asserts a precision
  the abstract does not have.
- **The payoff is the crossover, not the clustering.** Compute the age at which
  weighted stance flips, and draw two lines — where the claim puts the threshold
  and where the evidence puts it. *"The claim says 12 months. The evidence
  crosses at 9.4."* Clustering shows it; the crossover states it.
- **Per-claim opt-in, by semantics first and null rate second.** 27 of 80 claims
  mention timing but only ~13 are genuine threshold questions. `honey_avoid_12m`
  has ages in 22% of abstracts — but it is a "does this hurt" question, not a
  timing one, so its null rate is not evidence against the axis.

---

<a id="d13"></a>
## D13 — How much of an abstract the model receives
**2026-08-29 · finding**

`evaluate_claims.py` cuts every abstract at 1,800 characters.

| | pairs | share |
|---|---|---|
| have an abstract | 7,769 | |
| truncated at 1,800 | 2,730 | 35.1% |
| losing 600+ characters | 836 | 10.8% |
| **CONCLUSION section removed entirely** | **675** | **8.7%** |

Structured abstracts put CONCLUSION last, so the truncation removes precisely
the sentence where the authors state what they found. On roughly one pair in
twelve the model is asked what a paper concluded with the conclusion deleted.

1,800 characters is ~450 tokens against context windows in the tens of
thousands — a leftover, not a constraint. 95th percentile is 2,886 chars.

**Fix before the bake-off, not after.** Otherwise some unknown share of every
candidate's error rate is "was not allowed to finish reading", and the
comparison measures a handicap rather than judgement.

*Found while checking a gold-set label. The label in question — a pacifier claim
scored against a bed-sharing paper — turned out to be a genuine model error
rather than a truncation artifact: the relevant sentence sat at char 1,475, well
inside the cut. The model saw it and inverted anyway.*

---

<a id="d14"></a>
## D14 — How a paper's influence on its claim is expressed
**2026-08-29 · decided**

Two signed numbers per card: how far this paper pulls the claim vertically
(support) and horizontally (quality).

**No per-paper share of the horizontal one exists.** `evidence_quality_of` is
`0.5 × mean(top quartile) + 0.35 × mean(top decile) + 0.15 × mean(all)`, so a
paper outside the top quartile contributes only through the 0.15 term. Compute
both as leave-one-out deltas instead: exact for any formula, survives the next
change to the weighting, and is literally the question the reader is asking.

**The wording must respect that leave-one-out influences do not sum to the
total** — the denominator moves. *"Remove this paper and the claim moves 4 points
down"*, never *"this paper contributes 4 points"*.

**Consequence to design around:** on a 150-paper claim ~145 cards read 0. That is
the true picture — a claim is usually decided by five papers — but two numbers
that are almost always zero is transparency nobody reads. So: a micro-vector on
every card (always visible, degrades gracefully, digits on hover), *and* a
top-five-movers list on the claim panel, which is the one a reader will use.

**Blocked by a bug:** `build_claims_data.py:314` passes `evidence_strength` where
`paper_weight` expects `study_type`, so every exported per-paper weight is
computed at the 0.30 unclassified fallback. The number on the card today is not
the number driving the claim's position.

---

<a id="d21"></a>
## D21 — What makes a paper evidence for a claim
**2026-08-29 · decided**

The evaluator asks one question — *does this paper support the claim?* — so
everything that is not supports/refutes/mixed lands in `neutral`. That bucket is
**2,435 of 7,769 pairs (31%)**, and it is three different things wearing one
badge:

- a paper that tested the claim and found nothing conclusive
- a paper that tested something *adjacent* to the claim
- a paper that is in the corpus by retrieval accident

Those need opposite treatment. The first is a real result and belongs on the map.
The second should count, discounted. The third should be dropped. Collapsing them
is why the evidence view's context box is filled by *failure* — a paper lands
there for fitting nowhere else, then wins a citation contest among the other
misfits.

**Decision: relevance becomes its own question with four tiers**, taken in order,
first fit wins:

| Tier | Means | On the map |
|---|---|---|
| `direct` | tests the claim — its population, its exposure, its outcome | plotted, full weight |
| `indirect` | tests a neighbouring question: older population, animal model, proxy outcome, related dose or route | plotted, discounted |
| `framework` | does not test the claim, but supplies a method, measure, definition, mechanism or guideline that a paper testing it would use | context section ([D10](#d10)) |
| `background` | mentions the topic, contributes nothing | dropped, counted, reported |

**The load-bearing rule, and the one a small model gets wrong unless told:**

> Relevance is about **what was measured**, never about whether the findings
> agree. A paper whose results destroy the claim is `direct`.

Without that sentence a 7B marks any abstract containing the word "peanut" as
directly testing early peanut introduction, and scores disagreement as
irrelevance.

**Why tiers and not a score.** Relevance is categorical, never a high/medium/low
degree. A degree scale invites exactly the topic-similarity judgement the model
already makes wrongly, and `framework` is not a *weaker* contribution than
`direct` — it is a different **kind** of contribution. Ranking them on one scale
would put the food-challenge protocol and a restaurant-labelling survey on the
same axis, which is how the current context box came to hold both.

**The boundary that needs a rule** is `framework` against `background`, since
both mean "does not test the claim". Two tests, in order:

1. **Can you name what it offers in one word** — method, measure, definition,
   mechanism, guideline? If you are straining, it is `background`. `framework`
   has to be earned or it becomes a bin for "interesting but does not fit".
2. **Would a paper testing this claim cite it in its Methods section?**
   `framework` papers get cited in Methods; `background` papers get a throwaway
   line in an intro, or nothing.

**Mechanism is the trap**, because it feels relevant whenever it concerns the
same outcome. A tool only counts if it serves *this* claim: a mechanism for the
claim's exposure→outcome pathway is `framework`; a mechanism for the outcome in
general that bypasses the claim's exposure is `background`. A wear-and-tear
theory of SIDS aetiology gives nobody testing *sleep position* anything to use.

**Early evidence that this is the dominant failure.** Of the first eight
human/model disagreements in gold-set labelling, **six were relevance rather
than stance** — papers that should never have been scored at all. That sample is
deliberately loaded with suspicious rows so the rate does not generalise, but it
shifts weight toward the screen pass ([D22](#d22)) relative to the stance fix
([D5](#d5)).

**Open: how much `indirect` is discounted.** Not a flat multiplier. A paper is
indirect for a *stated reason* — older population, animal model, proxy outcome,
different dose, different route — and those do not discount equally: an animal
model is a different kind of distance from a three-year-old cohort. Store the
reason as an enum so the discount can be per-reason, and set the values against
the gold set rather than by taste.

**What would change our mind:** the gold set. If `indirect` papers agree with
hand labels as often as `direct` ones do, the tier is not earning its discount
and the distinction collapses to a two-way one. And if `framework` cannot be
applied consistently by two human labellers, it is not a category — it is a
feeling, and it should be merged into `background`.

---

<a id="d22"></a>
## D22 — How the relevance and stance questions are put to the model
**2026-08-29 · decided**

Given [D21](#d21), relevance and stance are two questions. They could still be
asked in one call.

**Decision: two calls, screening gates stance.**

```
SCREEN  ──> relevance + population/exposure/outcome + age window
   │
   ├─ direct | indirect ──> STANCE  (finding → direction → verdict)
   └─ framework | background ──> stop. recorded, never evaluated.
```

**It roughly pays for itself.** ~31% of pairs never reach the stance call, so the
cheap screen gates the expensive judgement rather than adding to it. It also
gives a small model **one job at a time**, which on the evidence of [D1](#d1) and
[D3](#d3) is the only way it does either job well.

Three consequences worth stating, because they are the real argument:

- **`neutral` narrows to something true.** It stops being the drain for
  everything unmatched and becomes only *"tested this and could not tell"*.
  Background papers never reach the stance question, so nothing they might have
  said can leak into a verdict. That is most of what makes today's `neutral`
  meaningless.
- **The two stages become independently re-runnable.** Re-scoring stance on a new
  model no longer means re-deciding relevance, and vice versa. At 14–25 hours a
  pass ([D7](#d7), [D17](#d17)) that is worth the extra parse surface on its own.
- **Failure gets a location.** A wrong verdict today could be either failure mode
  and there is no way to tell from the record. Split, the screen's answer is
  stored separately, so a bad row says which stage produced it.

**Extract the age window on every paper, not only on timeline claims.** It is a
relevance signal everywhere — a study of five-year-olds is `indirect` for an
infant claim — and at 14–25 hours a pass there will not be a cheap second chance
to collect it. The same argument applies to population, exposure and outcome:
they are needed for [D8](#d8)'s conflict matching, and collecting them costs
nothing extra once the screen is being run.

**What would change our mind:** the gold set, on two counts. If screening on a
~20B model costs as much as stancing, the cost argument weakens to nothing and
one call is simpler. And if a single decomposed call ([D5](#d5)) scores as well
as the split on both relevance and stance, the split is buying only the
re-runnability — still worth something, but not the same case.

---

<a id="d15"></a>
## D15 — What the journal a paper appeared in is worth
**2026-08-23 · rejected (as a verdict weight)**

*Entries D15–D20 predate D1–D14; they document decisions taken while the map was
being built, written up afterwards. Appended rather than renumbered — see the
header.*

The proposal was to let the journal a paper appeared in count toward how much
that paper moves the claim. OpenAlex carries the metric — not "Impact Factor",
which is Clarivate's trademark, but `summary_stats.2yr_mean_citedness`, the same
calculation, free and licence-free. `h_index` and `i10_index` come in the same
payload.

**Measured on this corpus's own top journals:**

| Journal | 2yr_mean_citedness | papers held |
|---|---|---|
| Nutrients | **5.99** | 274 |
| Cochrane Database | 7.11 | 66 |
| PEDIATRICS | 4.81 | 72 |
| PLoS ONE | 3.12 | 95 |
| **Archives of Disease in Childhood** | **1.96** | 105 |
| **BMJ** | **0.00** | 29 |

It ranks *Nutrients* — an MDPI mega-journal publishing ~39,000 papers a year —
three times above *Archives of Disease in Childhood*, the BMJ's paediatrics
journal and the second-largest source in the corpus. *PLoS ONE* also outranks it.
And the BMJ scores zero, because the metric is simply missing for it.

**Rejected as a verdict weight on three grounds:**

1. **We already use something strictly better.** A paper's own citation count
   measures that paper's uptake. A journal average measures its neighbours, and
   within-journal citation distributions are extremely skewed — which is the
   substance of the DORA critique. Adding it means partly replacing a direct
   measurement with a noisier proxy for the same thing.
2. **It biases across topics.** PEDIATRICS 4.81 against NEJM 30.59 is a sixfold
   spread that reflects field size, not evidence quality. The map compares claims
   across 14 topics, so a journal term shifts whole topics for reasons unrelated
   to what it claims to measure.
3. **Design already carries the signal.** Cochrane scores highest precisely
   because it publishes systematic reviews — which [D16](#d16)'s ladder already
   puts at 1.00. What remains after design is largely noise plus field bias.

**What is in use, and why it is a different question.** `importance_of` weights
it at 0.20 alongside design (0.45) and within-claim citations (0.35), on a log
scale against a ceiling of 20. That answers *"which of these should I read
first"*, where a journal's track record is legitimate prior information. It does
not touch `paper_weight`, so it never moves a claim. Keep that separation.

**Live consequence to be aware of.** 110 of 1,948 journals (5.6%) score
`impact = 0` or null, and `journal_norm = log1p(0)/log1p(20) = 0` — the floor,
indistinguishable from a genuinely obscure venue. The largest is the **BMJ, with
29 papers**, h-index 613. If ranking ever looks wrong on a BMJ paper, this is
why. A missing metric should probably fall back to the corpus median rather than
to zero, or to `h_index` scaled, since that field is populated where the 2-year
one is not.

**What would change our mind:** a use for it as a *prior where citations do not
yet exist*. 8% of judged papers have under five citations, and that rises with
recency — 35% of 2024 papers, 54% of 2025, 93% of 2026. A brand-new trial in a
serious journal is currently weighted like an obscure one purely because it has
not had time. Blending the journal metric in for papers under about two years
old, decaying to nothing as real citations arrive, uses it for the one thing it
is actually defensible for. That is a different proposal from this one and is not
rejected here.

---

<a id="d16"></a>
## D16 — What ranks an individual paper's quality
**2026-08-23 · decided**

The horizontal axis was driven by the model's own `evidence_strength`
(`strong`/`moderate`/`limited`), mapped to 1.0 / 0.5 / 0.0. Two faults.

**It conflates design with size.** The prompt defines the label as *"strong =
meta-analysis/large RCT; moderate = smaller RCT or prospective cohort"*, so a
sound but modest RCT scores "moderate" and lands dead centre. 37 of 195 RCTs
were labelled that way. This is what a reader notices first.

**Worse, the resulting order was not a hierarchy.** Mean X position, measured
over 3,900 judged papers:

```
position paper              1.00     <- above meta-analyses
report                      1.00
meta-analysis               0.93
rct                         0.89
case-report                 0.74     <- above cohorts
cross-sectional             0.71     <- above cohorts
cohort                      0.69
randomized controlled trial 0.66     <- below case reports, purely because the
                                        model spelled it out instead of "rct"
narrative review            0.50
```

`study_type` was stored but never touched the axis. The model had also invented
**154 distinct `study_type` strings**, with RCTs spread across twenty spellings.

**Decision.** `backend/design.py` normalises the free text into a canonical
design and ranks that on a conventional evidence hierarchy. The model still does
the reading — it reliably spots that a paper randomised people — it just no
longer decides what that is worth. 1.8% end up unclassified.

```
meta-analysis      1.00      cross-sectional    0.30
randomised trial   0.88      review             0.24
controlled trial   0.72      case report        0.20
prospective cohort 0.60      animal or lab      0.14
cohort             0.50      opinion / guidance 0.12
case-control       0.40      protocol           0.08
```

Two placements that are deliberate rather than obvious:

- **Protocols rank lowest of all.** A protocol for a trial is not the trial; it
  has no results. Twenty were scoring as evidence.
- **Guidelines and position papers sit near the bottom** — not because they are
  worthless but because they are not studies, and several are plausibly the very
  source a claim was written from. Counting them as evidence *for* that claim is
  close to circular. Whether they belong in the corpus at all is still open.

This also drives `paper_weight`, so `netSupport` weights by design rather than by
the same broken label. It needed no re-evaluation: `study_type` was already
stored for every judged pair.

**Verified at the time:** a claim's X remained exactly the mean of its papers' X
— worst gap 0.0005 — so the anchor sat at the centroid of the cloud beneath it.

> **Superseded 2026-08-26 — this property was deliberately given up.** A claim's
> X is no longer the mean of its papers'; measured on the current build the worst
> gap is **0.435** and **79 of 80** claims differ by more than 0.10. That is
> intended, not a regression: see [D20](#d20). The rest of this entry — the
> ladder, and design rather than the strength label as what ranks a *paper* —
> stands unchanged. D16 is about ranking one paper; D20 is about aggregating many
> into a claim.

**Amended 2026-08-26 — the label is no longer shown to readers either.** This
entry removed `evidence_strength` from the axis but left it badged on the paper
panel, beside the design it duplicates and contradicts. Measured over the
completed corpus, of 3,393 rows labelled `strong` only **16.9%** are a
meta-analysis or RCT and **20.5%** are designs the prompt's own wording calls
*limited*; cross-sectional studies drew `strong` 499 times against `limited` 42.
The badge is gone from the interface. The field stays in the database, because
it is the input to the audit that condemned it.

**What would change our mind:** a model that returns a clean design enum rather
than free text would make the normalisation layer unnecessary, though not the
ladder. And the ladder's *numbers* are a convention, not a measurement — if the
gold set ever shows the ordering mis-serving real claims, the rungs are the thing
to move, not the principle.

*Cheap mistakes found building this, both by checking the classifier against real
strings rather than trusting the regexes: `\breport\b` matched "case-report"
across the hyphen and filed 88 case reports as opinion pieces; a `\bcase\b`
shortcut turned every "case-control" into a case report.*

---

<a id="d17"></a>
## D17 — Whether a full pass can be made faster
**2026-08-23 · finding**

The obvious response to a 14–25 hour pass ([D7](#d7)) is to run several workers
at once. It was tried.

```
serial                   12 pairs in 1.0 min
4 workers, 4 shards      40 pairs in 3.4 min
```

Identical throughput. Local inference on Apple Silicon is **memory-bandwidth
bound**, and one mistral stream already saturates it; concurrency divides the
same bandwidth rather than adding any. `OLLAMA_NUM_PARALLEL=4` changes nothing
about that.

**So D7's cost arithmetic has no escape hatch on this hardware.** A full pass
costs what it costs, and the levers are model size, prompt structure and how many
pairs need judging — not concurrency.

The work done to make concurrent runs *possible* was still worth keeping, because
it fixed a real bug rather than only enabling the experiment: `evaluate_claims.py`
held a write transaction across five LLM calls (~25 s) while committing in
batches of five, so any second process died on `database is locked`. It now
commits per row under WAL with a 60 s busy timeout, which also makes an
interrupted run resumable to the exact pair rather than the last batch.

**What would change our mind:** different hardware. A discrete GPU with headroom,
or a machine with more bandwidth than one stream can consume, changes the answer
immediately. So would batched inference — submitting many prompts in one request
so the server can fill the batch dimension — which is a different mechanism from
running several clients and is untested here.

---

<a id="d18"></a>
## D18 — How verdicts are lost between the model and the database
**2026-08-24 · finding**

`parse_json_response` reads the model's reply. Its salvage path — for a reply
wrapped in prose or fences — is `re.search(r"\{.*\}", text, re.DOTALL)`, which
needs a closing brace to match at all. A reply that stopped one character short
therefore failed both paths and was discarded whole:

```
  "evidence_strength": "limited",
  "study_type": "review"        <- ends here. no closing brace.
```

Every field present, every field correct, thrown away over one character.

**It was not transient, and re-running never helped.** The evaluator runs at
`temperature=0.0`, so the same abstract fails the same way every pass. 19 of 19
re-tried pairs failed identically before this was understood; the resume flag
was doing nothing but spending inference to reproduce the same loss.

**And the loss had a direction.** 80 pairs were affected. Balancing the braces
and re-parsing recovered 79 — and they came back **72 neutral out of 79**,
because a hedged answer carries a longer `finding` and is the one that runs out
of room. The parser was quietly biasing the corpus toward papers that took a
side.

**On the magnitude, honestly:** 79 rows in 7,769 is about 1%. This does *not*
move [D1](#d1)'s numbers and should not be offered as an explanation for them.

**Why it is logged anyway** — the mechanism, not the size. This is a silent,
deterministic, direction-biased loss channel between the model and the database,
and it is invisible from either end: the model produced a good answer, the
database simply has no row. It bears directly on [D6](#d6). A bake-off scores
candidates on rows that came back; a candidate losing rows this way scores as
though it judged them wrong, and the ruler measures plumbing instead of
judgement.

**What would change our mind:** nothing about the fix, but the general form is
worth holding. Any pipeline stage that can drop a record without raising should
count what it dropped and say so — `evaluate_claims.py` reports `failed N` and
that number was visible in every run log for weeks without anyone asking what
was in it.

---

<a id="d19"></a>
## D19 — Whether colour can carry meaning legibly
**2026-08-25 · decided**

The stance palette runs `#d64545` (refutes) through `#94a3b8` (neutral) to
`#2e9e5b` (supports). Putting white type on it — the obvious way to label a
card by its verdict — fails WCAG AA at **every point on the scale**:

| net | colour | white on it | AA normal (4.5:1) | AA large (3:1) |
|---|---|---|---|---|
| −1.00 refuted | `#d64545` | 4.38 | fail | pass |
| −0.25 | `#a58c9b` | 3.08 | fail | pass |
| **0.00 neutral** | `#94a3b8` | **2.56** | fail | **fail** |
| +0.50 | `#61a18a` | 3.01 | fail | pass |
| +1.00 supported | `#2e9e5b` | 3.41 | fail | pass |

The midpoint is the worst of it, and **26 of 80 claims sit in that pale middle**.
The same check found the verdict text on the paper cards already failing at
**3.41:1** before any of this work — the palette had been used directly as a text
colour since it was written.

**Decided.** Text never takes a palette colour directly. It takes a derivative,
darkened in HSL — hue preserved, so red still reads red and green green — until
it clears the ratio. Where a fade is wanted, what varies is the **contrast
target**, not the opacity: opacity multiplies against the background and drops a
4.5:1 colour under the floor immediately, whereas ramping the target from 4.5:1
to 10:1 gives the same visual recession with the weakest element still exactly at
the standard. And colour is never the only channel — every card that is tinted by
its verdict also spells the verdict out.

**Why it is a decision and not a bug fix:** it constrains the palette. Any future
encoding that wants to put text on a stance colour inherits this, and the
temptation — a tinted card with white type on it — is the specific thing that
does not work. Recorded so it is not rediscovered by shipping it.

**What would change our mind:** a palette chosen for contrast from the start
rather than for hue. The diverging red-grey-green scale is doing real work and
was not picked with type in mind; a scale with a dark end would make the
derivation unnecessary. That is a bigger change than it sounds, because the same
colours are load-bearing for the dots.

---

<a id="d20"></a>
## D20 — How a claim's position aggregates its papers'
**2026-08-26 · decided · supersedes part of [D16](#d16)**

[D16](#d16) ranks one paper by its design. This is the separate question of what
a *claim's* X should be, given the ranks of the papers under it — and until now
the answer was the plain mean, which D16 verified as the centroid of its cloud.

**The mean is the wrong average for this.** A question settled by two
meta-analyses is settled; averaging them against sixty cross-sectional studies
reports the state of the *literature* rather than the state of the *answer*. The
visible cost was that all eighty claims sat in 0.27–0.80 averaging 0.40, so the
map lived left of centre and the right-hand half of the axis went unused.

Measured across the whole corpus:

| aggregation | range | mean | claims per fifth of the axis, L→R |
|---|---|---|---|
| mean of all (was) | 0.27–0.80 | 0.40 | huddled left |
| 70% top quartile + 30% mean | 0.20–0.88 | 0.59 | `1, 3, 36, 38, 2` |
| **50% top quartile + 35% top decile + 15% mean** | **0.20–0.91** | **0.69** | `0, 1, 15, 49, 15` |
| 80% top decile + 20% mean | 0.20–0.91 | 0.74 | `0, 1, 4, 45, 30` |
| max | 0.50–1.00 | 0.95 | one meta-analysis owns the claim |

The maximum overcorrects into meaninglessness — nothing is distinguishable from
anything. Leaning on the top decile alone piles thirty of eighty claims into the
far-right fifth, which stops being a ranking. The shipped weights are the middle
course, and each term has a job: the **top decile** gives the strongest handful
of papers a say of their own, the **top quartile** stops any one of them owning
the claim (on a 180-paper claim that quartile is 45 papers), and the **overall
mean** keeps fifty strong studies ahead of three strong and two hundred weak.

**Result.** The claim sits right of its median paper on **77 of 77** claims with
enough papers to judge. Claims with no strong work stay left, which is the check
that matters: `restrictive_devices` 0.20, `crawling_not_required` 0.42,
`honey_avoid_12m` 0.43.

**What was given up.** D16's centroid property. A claim's X is no longer the mean
of its papers' X — worst gap 0.435, and 79 of 80 claims differ by more than 0.10.
The anchor on the evidence view now sits deliberately to the right of the cloud
beneath it, which has to be *said* on that screen rather than left for a reader
to notice as an inconsistency. It is not yet said; see `BACKLOG.md`.

**What would change our mind:** the gold set, again. These weights are a
convention chosen against the shape of one corpus, and if the relevance tiering
([D9](#d9)) removes the weak tail that the mean was drowning in, the argument for
weighting the top so heavily gets weaker — the top quartile of a *tiered* corpus
is a different population from the top quartile of this one.


---

<a id="d23"></a>
## D23 — What a paper card shows, and what the map encodes twice
**2026-08-30 · decided**

The evidence view draws a paper as a card that is compact until hovered or
pinned. Compact, it carried a `#rank` and — only where the card was at least
124px wide — a design label. Measured across all 80 claims, **12% of cards clear
that width** (median 12% per claim), so on roughly seven cards in eight the
entire content was a rank number, with no way to find out what produced it.

**Audit of what the six channels encode.** Asked directly, rather than one
channel at a time as they were added:

| channel | encodes |
|---|---|
| X position | design rank |
| fill / stroke opacity | design rank |
| size | importance |
| `#n` text | importance |
| colour | stance |
| Y position | stance x confidence |

Two quantities are drawn twice and two are never drawn. **Citations and the
journal metric together carry 55% of the weight in `importance_of` and do most
of the actual ordering** — median rank-correlation with the final order is
citations +0.62, journal +0.48, design +0.45 — and neither has a channel.
Publication year has none unless the X switch is thrown.

The design ladder is lumpy, which is why the weaker-weighted term out-orders it:
twenty rungs with most papers piled on a handful, so design produces large ties
that citations then break.

**The rank and the X position are different quantities, and diverge visibly.**
X is `designRank` alone; the rank is all three terms. So:

- on **29%** of claims the `#1` paper is *not* the rightmost on the axis;
- on the median claim, **19% of paper pairs** have the better-ranked one sitting
  further left.

On `peanut_intro_early` the top three are #1 at x=0.88, #2 at x=0.88, #3 at
x=1.00 — the meta-analysis is furthest right and ranks third. A reader who has
learned "right is better" gets a contradiction the screen never resolves.

**Decided: keep the setup, explain it on the open card.** The redundancy is not
a fault to remove — size and rank are the same quantity in a coarse channel and
a precise one, which is how a reader finds the important papers by eye and then
confirms by number. What was missing was any account of the arithmetic. The open
card now shows the three terms, each with the contribution it made and the most
it could have made:

```
WHY IT RANKS #1 OF 151
▬▬▬  study design   meta-analysis   0.45 / 0.45
▬▬   citations      1,272           0.27 / 0.35
▬▬   journal        impact 7.33     0.14 / 0.20
                          importance 0.86 / 1.00
```

The three contributions are computed in the backend and exported as
`importanceParts`, not recomputed on screen: the citation term is normalised
across every paper held for the claim, and the frontend has already dropped most
of the neutrals by the time it draws anything — a second implementation would
quietly disagree with the ranking it is explaining. Design, journal and citations
were removed from the card's bare detail row at the same time, because stating
them twice within 20px teaches nothing the second time.

Context papers are excluded: they are ranked by the same arithmetic but never
placed in the plot, so explaining a position they were not given raises a
question the screen cannot answer.

**The weights are on screen because they have never been calibrated.** `0.45 /
0.35 / 0.20` appear nowhere in this file as a decision — [D15](#d15) mentions
them only in passing while describing what the journal term does. They are a
starting point that has been rendering as a result for weeks. Printing them
where a reader can see them makes that checkable by someone who does not read
the source, and is the cheapest available pressure to go and calibrate them.
`W_DESIGN` / `W_CITATIONS` / `W_JOURNAL` in `build_claims_data.py` now name them
so there is one place to change.

**What would change our mind:** the gold set. It ranks nothing today — it labels
stance — but a "which of these should I read first" question put to the same 60
pairs would turn the weights from a convention into a measurement. Until that
exists, any argument about 0.45 against 0.40 is taste.

---

<a id="d24"></a>
## D24 — Whether a paper's age should affect its rank
**2026-08-30 · decided**

**No recency term.** A recency bonus asserts that newer is better, which is
false for this corpus — the 1998 landmark trial is often exactly the paper a
reader should open first, and `peanut_intro_early` is ranked correctly precisely
because LEAP (2015) outranks everything published since.

**But there is a real age skew, and it is not about recency.** Median rank
percentile by publication year, over the 7,768 judged pairs (0.00 = top of the
claim's list):

| 2014 | 2016 | 2018 | 2020 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|
| 0.38 | 0.41 | 0.43 | 0.44 | 0.55 | 0.57 | **0.67** | **0.73** | **0.83** |

Flat at 0.44 or below for everything up to 2021, then it falls off a cliff. A
2025 paper sits in the bottom third of its claim **by construction**. That is
not a judgement about new work; it is `log1p(citations)` measuring elapsed time,
exactly as [D15](#d15) predicted when it recorded that 54% of 2025 papers and
93% of 2026 papers have under five citations.

So the fix belongs in the citation term, not in a new one. Two candidates, both
removing the skew without claiming new is good:

1. **Age-normalise the citations** — percentile within publication year, or
   citations per year since publication.
2. **[D15](#d15)'s own proposal** — blend the journal metric in as a prior for
   papers under about two years old, decaying to nothing as real citations
   arrive. This is the one use of the journal metric D15 did not reject.

Neither is chosen here; both are in `BACKLOG.md` behind calibrating the weights,
since changing the citation term and the weights independently means measuring
the same thing twice.

**What would change our mind:** evidence that readers want the newest work
first regardless of uptake — which would be an argument for a *year filter*,
still not for a recency term in a reading-order rank.
