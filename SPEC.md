# Map of Baby Science — Specification

**Project:** mapo_baby_food
**Repository:** TomHirsch3000/mapo_baby_food
**Last updated:** 2026-08-29

> This document states what the project is *for* and the rules it holds itself
> to. Where it describes mechanism, it does so because the mechanism follows
> from an intention — not as a record of what happens to be built. Anything
> here that the code contradicts is a bug in the code or a decision that needs
> revisiting in this document first.
>
> It is deliberately not a history. What was measured, what was chosen and why
> lives in `DECISIONS.md`, which is append-only; what is still to do lives in
> `BACKLOG.md`, which shrinks.
>
> **The test that keeps them apart: delete `DECISIONS.md`, and this document
> must still be enough to rebuild the system correctly.** So every decision that
> has *shipped* leaves a line or two here stating the rule — the evidence, the
> numbers and the alternatives stay in the entry it cites. A decision that has
> been taken but not built belongs in `BACKLOG.md`, not here: this document
> changes when the code does, so that it never describes a system that does not
> exist.

---

## 1. What this is

A map of the scientific evidence behind the claims people make about raising
children.

Parents are handed advice constantly — from health visitors, forums,
grandparents, articles, each other — and almost none of it arrives with any
indication of how well established it is. "Don't give honey before one" and
"screens rot their attention span" are delivered in the same confident tone,
though one is a settled matter of infant botulism and the other is a contested
correlation. The gap between *how confidently a claim is stated* and *how well
the evidence supports it* is the thing this project exists to close.

### The goal

**To inform the discussion about raising children with scientifically backed
information, presented coherently and digestibly, without losing integrity or
the link to the sources and the quality of the evidence underneath.**

Every word of that is load-bearing:

- **Inform the discussion** — not settle it. This is not an authority handing
  down verdicts; it is a map of what has actually been studied and what was
  found. A contested claim should *look* contested.
- **Coherently and digestibly** — the whole point is doing the work so the
  reader does not have to. If someone has to already understand
  meta-analysis hierarchies to use this, it has failed.
- **Without losing integrity** — no simplification that makes the picture
  cleaner than the evidence is. Uncertainty gets rendered, not smoothed away.
- **The link to the sources** — every claim decomposes into the actual papers,
  every paper links out. Nothing is asserted that cannot be traced.

### Who it is for

Primarily parents making real decisions. Secondarily anyone arguing about
child-rearing who would like to know what the literature says. The design
target is someone intelligent and motivated but without research training,
reading on a laptop, with limited time and a baby in the room.

### What it is not

- Not medical advice, and it must never read as though it is.
- Not a systematic review. It samples the literature; it does not exhaust it.
- Not neutral about quality. A finding from a 40-study meta-analysis and one
  from a cross-sectional survey of 60 people are not shown as equals.

---

## 2. Principles

These constrain every design decision that follows. When a feature and a
principle conflict, the principle wins.

**1. Show the evidence, not a verdict.**
The map never says "true" or "false". It shows how much evidence exists, which
way it points, and how good it is. The reader draws the conclusion.

**2. Uncertainty is information, and must be visible.**
A claim with three weak supporting studies and two strong refuting ones is one
of the most useful things this map can surface. It must not be averaged into a
confident-looking dot.

**3. Never hide the gap between what was asked and what was tested.**
People search in the words they use ("should I avoid screens under two?").
Studies test measurable propositions ("is screen exposure before 24 months
associated with worse developmental outcomes?"). Both must be shown; the
translation between them is never silent.

**4. Every automated judgement must be auditable.**
Stances are assigned by a language model. That is acceptable only if the
reasoning behind each one is stored and shown, so a reader can see *why* a paper
was badged as it was, and catch it when the badge and the reason disagree.

**5. Absence of evidence is displayed, not omitted.**
A claim nobody has studied is a finding. Unresearched claims appear on the map
at their true size, visibly unassessed — never quietly dropped so the map looks
more complete than it is.

**6. Position means the same thing everywhere.**
A reader learns the axes once. Their meaning does not change between screens.

**7. Nothing on screen is unexplained.**
Every colour, size and position encodes something, and the reader can find out
what without leaving the page.

---

## 3. The three levels

The map is one drill-down, three levels of abstraction:

```
TOPICS      the areas of decision-making in raising a child
   |        hexagons, tessellated
   v
CLAIMS      the common claims within one topic
   |        scatter: how true (Y) against how good the studies are (X)
   v
EVIDENCE    the published papers behind one claim
            same scatter, one level down, plus the claim itself as an anchor
```

### 3.1 Topics

The activities and decisions that actually occupy parents — food, sleep,
screens, activity, learning — as tessellating hexagons. Hexagons tile without
gaps, which says something true: these are neighbouring parts of one continuous
subject, not separate silos.

Because tessellation forces uniform size, node size cannot encode anything
here; counts go in the label instead. Each hexagon reports how many claims it
holds and how much has been published on them.

It also reported how many of those claims had been researched, until every claim
carried a verdict and the counter read "7 claims · 7 researched" on all fourteen
topics. A number that cannot vary is not information. It belongs back the moment
coverage is partial again — a new topic, or a batch of claims added ahead of the
papers that answer them — and the field is still exported for that. Principle 5
is unchanged; what carries it on this screen for now is the gap between how much
exists on a topic and how much is held.

Topics are grouped into themes — eating, sleeping, playing and learning, screens
— each tessellating on its own with a gap between them. A parent arrives already
thinking "feeding" or "sleep", so the grid answers that before it answers
anything else.

Topics should cover the territory a parent recognises, not the territory
academia is organised into. If a parent worries about it, it belongs.

### 3.2 Claims

The common claims within a topic, on two axes:

| | Encodes | Reads as |
|---|---|---|
| **Y** | net support | supported at the top, refuted at the bottom, contested in the middle |
| **X** | evidence quality | weak study designs left, strong ones right |
| **Size** | volume of literature | how much has been published on this question |

The quadrants are the point:

- **top-right** — settled: supported by strong studies
- **top-left** — promising: supported, but only by weak ones
- **bottom-right** — debunked: refuted by strong studies
- **bottom-left** — doubtful: refuted, but only by weak ones
- **centre** — genuinely contested

**X is where a claim's *best* evidence sits, not its average.** A question
settled by two meta-analyses is settled; averaging them against sixty
cross-sectional studies reports the state of the literature rather than the state
of the answer, and put every claim in the left-hand half of the axis. The
aggregate is weighted to the strongest quarter and tenth of the papers, with the
overall mean kept as a check — see `DECISIONS.md` D20.

**Size deliberately tracks the literature, not our holdings.** A claim with
thousands of papers published and none yet collected appears large and
unassessed. That gap is the most honest thing the map can show about its own
coverage.

Claims phrased as advice ("X should be avoided before N months") keep that
wording, because that is how people search. The empirical proposition the
evidence was actually graded against is shown alongside it — see §5.

### 3.3 Evidence

The papers behind one claim, on the *same* axes, so nothing is relearned:

| | Encodes |
|---|---|
| **Y** | the paper's stance, scaled by the evaluator's confidence |
| **X** | strength of the study design — switchable to publication year |
| **Size** | importance — how much this paper is worth reading first |
| **Colour** | stance |

Y is signed confidence rather than bare stance because a 95%-certain refutation
and a hesitant 60% one are not the same claim on the reader's attention.

Size was citations alone. It now combines study design, citations relative to
this claim, and the journal's own record — because "which of these should I read
first" is the question a hundred papers actually raise, and no one of those three
answers it: design alone ranks a tiny flawless trial over a definitive
meta-analysis, citations alone reward age, and the journal says nothing about the
specific paper. Each card carries its resulting position in that order. The
journal term ranks and never weights a verdict; the reasoning for that separation
is `DECISIONS.md` D15.

**A rank has to show its working.** Opened, a paper card names all three terms
with the contribution each made and the most it could have made, ending at the
importance score itself. The weights are stated on screen rather than only in
the source, because they have never been calibrated — a number a reader can
check is the only honest way to ship one that has not been earned yet
(`DECISIONS.md` D23). The three contributions are computed once, in the export,
and travel with the paper: the citation term is normalised across every paper
held for the claim, and re-deriving it in the browser — which has already
dropped most of the neutrals — would explain the ranking with different
arithmetic from the one that produced it.

X and this rank are **not the same quantity**, and a reader will find cases where
they disagree: X is the design term alone, the rank is all three. On 29% of
claims the top-ranked paper is not the rightmost one. That is the breakdown's
main job — without it the disagreement looks like a fault.

Context papers get no breakdown. They are ranked by the same arithmetic but sit
outside the plot, so explaining a position they were never given would raise a
question the screen cannot answer.

**The claim descends with you.** It wears the same card it wore one level up —
the same header, the same counts — so drilling in reads as one object moving
rather than a new one appearing, and it is pinned at the coordinates it held
there.

Since those coordinates now favour a claim's strongest studies (§3.2), the
anchor sits deliberately to the right of most of the cloud beneath it. That is
the one place on the map where a position is *not* comparable to the positions
around it, so it has to be said on the screen rather than inferred.

Citation edges run in the direction influence flows: from the older, cited paper
to the newer one citing it. Only the edges touching the context box are drawn: a
paper-to-paper citation says one author read another and nothing about whether
either is right or on topic, and at a hundred papers those edges are most of the
ink.

Papers that took no position on the claim are filtered out unless the claim's
own literature treats them as load-bearing, judged by how often the other papers
cite them. The bar is relative to each claim, because citation density varies
enormously between fields. What was filtered is always reported.

---

## 4. How evidence is judged

Papers are collected per claim from OpenAlex, then each (claim, paper) pair is
classified by a locally-run language model.

### Stances

| Stance | Meaning |
|---|---|
| `supports` | the findings agree with the claim |
| `refutes` | the findings disagree with it |
| `mixed` | the findings point **both ways** |
| `neutral` | the paper does not test the claim |

`mixed` is a first-class verdict, not a hedge. A meta-analysis can find that
screen *quantity* harms language while *quality* helps it; forcing that into
supports-or-refutes discards the most interesting thing it says and hands the
reader a confident badge the abstract does not earn.

### The three readings

A two-sided paper has no single honest position on a supported/refuted axis, so
the map does not pick one. It ships all three readings and lets the reader
choose:

| Reading | A mixed paper counts as | The stance it takes |
|---|---|---|
| **Conservative** | supporting | technically the claim holds, caveats aside |
| **Balanced** | neither | a two-sided paper takes no side |
| **Liberal** | refuting | the caveats weigh as much as the headline |

**The spread between the three is itself the signal.** A claim that reads +0.6
under one and −0.1 under another is not a settled claim, whatever its middle
number says.

### Weighting

A paper's contribution is `study quality × log(citations) × evaluator
confidence`. Quality dominates, impact is compressed so a single famous paper
cannot swamp a field, and low-confidence judgements pull their punches. Papers
that took no position never contribute to the verdict.

**Study quality means the design, on a fixed hierarchy — never the model's own
assessment of it.** The evaluator reports what a paper *is* (it reliably spots
that a study randomised people); a canonical ladder decides what that is worth,
from meta-analysis at the top down through cohorts to opinion and protocols at
the bottom. The model's `strong`/`moderate`/`limited` label touches neither the
axis nor the weighting, because it conflated design with sample size and ranked
position papers above meta-analyses. See `DECISIONS.md` D16.

### Auditability

The evaluator is asked to restate the paper's finding and commit to a direction
*before* it picks a stance. Both are stored and both are shown to the reader.

This is non-negotiable under Principle 4. A stance is a claim the map makes on
its own authority; the reasoning is what makes that claim checkable. It also
makes the failure mode findable in bulk: when the stored summary and the stored
stance disagree, the record is wrong and can be flagged by query rather than by
re-running inference.

**Known limitation.** Small local models invert on prescriptive claims — given
an identical abstract and an identical extracted finding, one will score
"refutes" against *"screens should be avoided before 18–24 months"* and
"supports" against *"screen exposure before 18–24 months is associated with
worse developmental outcomes"*. This is why §5 exists.

It is worse than §5 alone can fix. The same inversion fires whenever a paper
reports the **complement** of the claim's exposure — "prone sleeping increases
the risk" against a claim that "back sleeping reduces the risk" — and there,
measured over the papers on `back_to_sleep` that take that form, the model
handles it correctly **exactly half the time**: nine right, nine wrong. A step
that is right 50% of the time is not a rule applied badly, it is no rule at all.

The visible cost is that the most settled claims in the corpus read as the most
contested ones. Among their best papers, `back_to_sleep` nets −0.02 and
`vitamin_k_birth` −0.04 — two of the least disputed findings in paediatrics,
rendered as open questions.

This is the single largest threat to the map's credibility, and it constrains
what may be built: any feature that renders a verdict — flagging contested
claims, linking opposing papers, showing a paper's influence — would ship as a
renderer for classification error until it is fixed. See `DECISIONS.md` D1–D5.

---

## 5. Two wordings, one claim

Every claim carries two forms:

- **the claim** — the wording people actually use and search for
- **what was tested** — the empirical proposition a study can measure

They diverge whenever a claim is prescriptive. "Honey should be avoided before
12 months" is advice; no paper tests advice. What papers test is whether honey
consumption before 12 months is associated with infant botulism.

Rewording the claim to match would be the easy fix and the wrong one: it hides
the claim from the person looking for it. **The reader gets the phrasing they
recognise; the model gets the phrasing it can judge; and the translation is
shown, not hidden.** Doing that work on the reader's behalf — and then being
transparent that it was done — is the whole proposition of the project in
miniature.

---

## 6. Architecture

### Shape

**A static site with an offline pipeline.** There is no backend, no API, no
database in production. The browser reads pre-built JSON.

This follows from the content: the evidence base changes when papers are
imported and judged, which is a deliberate batch operation, not a per-request
one. A server would add cost, latency and failure modes to answer questions
whose answers were already known at build time.

```
OpenAlex ──> claims.db ──> static JSON ──> browser
          import      evaluate    build
```

| Stage | Does |
|---|---|
| **import** | collect papers per claim from OpenAlex |
| **evaluate** | classify each (claim, paper) pair with a local LLM |
| **build** | export the database to per-screen JSON |

Each stage is resumable and idempotent. None may require the previous one to be
re-run to make progress.

**A successful build is not evidence that anything renders.** The bundler does no
temporal-dead-zone analysis and no cross-scope identifier resolution, and d3
throws at run time on conditions it cannot see — an edge naming a node that was
filtered out takes down the whole view rather than dropping one line. Three
separate blank screens shipped past a clean `vite build` during development. So
the gate before publishing is `npm run smoke`, which mounts the real app in
jsdom and drives it — all three levels, the axis and reading controls, selection
and deselection, back navigation, search, the two-tap touch path, the information
panel, and a mobile viewport — failing on any error thrown from a render or an
effect. It runs in CI ahead of the deploy step, and a build that has not passed
it has not been shown to work.

### What lives in git

The **built JSON**, carrying every verdict *and the reasoning behind it* — and a
**vacuumed snapshot of the database** alongside it.

This is a deliberate durability decision, not an accident of `.gitignore`.
Verdicts cost hours of local inference to produce, so they must survive a move
to another machine without being recomputed — and recomputation is not even
neutral, since a different model build will quietly score the same abstract
differently and churn conclusions that are already published.

Consequence: JSON is the durable record, the live database is a working
artifact, and there must always be a path to rehydrate the second from the
first.

The snapshot is a convenience on top of that, not a replacement for it. It is
committed because a vacuumed SQLite file lays its pages out deterministically,
so git deltas successive versions down to roughly 20 KB per 300 new verdicts
against a 4.4 MB first commit — cheap enough that moving between machines needs
no file transfer, no cloud account and no re-import. The *live* database stays
out of git: it runs in WAL mode, so recent commits sit in a sidecar file and it
cannot be copied consistently while anything is writing to it.

### Costs and limits

OpenAlex bills a **flat rate per request** regardless of how much comes back.
The free tier is effectively 100 requests per day. Requests must therefore be
made as large as the API allows and never spent twice — in particular, never
spent on a value that a request already being made would have returned.

Paid credit is measured in pennies for this project's entire corpus. The free
tier's real function is to cap rebuilds at roughly one per day.

Evaluation runs locally, so it costs time rather than money — hours per full
pass. That is the binding constraint on iteration, which is why the taxonomy
should be settled before a full pass rather than during one.

---

## 7. Interface rules

- **Light, calm, uncluttered.** The subject is anxious enough.
- **Stance is vertical everywhere.** Up is more supported. This never changes.
- **Nothing encoded twice.** Size, position and colour each carry one thing.
- **Type never takes a palette colour directly.** The stance scale is chosen for
  hue, and white on it fails AA at every point — 2.56:1 at the neutral midpoint,
  where a quarter of the claims sit. Text takes a darkened derivative of the
  colour instead, hue preserved. Where something must recede, what varies is the
  contrast *target*, never the opacity: the weakest element still clears 4.5:1.
  And colour is never the only channel — anything tinted by its verdict also
  says what the verdict is. See `DECISIONS.md` D19.
- **Legible zoomed out.** Axis orientation must be readable when the whole map
  is on screen, so cluster shape can be understood before any label is.
- **Detail on demand.** The bottom panel shows whatever is under the cursor and
  holds whatever was clicked. Drilling in is a click; nothing is buried deeper.
- **Explain in place.** The reader can find out what the map is and how to read
  it without leaving it (§8).

---

## 8. Explaining the map to the reader

The map is dense and its axes are unusual. A reader who does not know that
vertical means support and horizontal means study quality sees a scatter of
dots.

The landing page therefore carries an **information panel**, reachable from a
persistent control, covering:

- what the map is and what it is for
- the three levels and how to move between them
- how to read the axes, sizes and colours at each level
- what "mixed" means and what the three readings do
- that stances are model-assigned, with the reasoning shown, and what that
  implies about trusting them
- that claims and tested propositions can differ, and why
- what the map does not cover, and that it is not medical advice

The limitations are not a footnote. Stating them plainly is what earns the rest
of it any credibility — a map that overclaims is worse than no map.

---

## 9. Open questions

- **Coverage.** Five topics and eighty claims is a starting shape, not a target.
  What makes the set complete enough to be trustworthy?
- **Judgement quality.** A small local model is cheap and private but errs in
  characterisable ways. What is the acceptable error rate, and how is it
  measured on an ongoing basis rather than by spot-check?
- **Recency.** Nothing currently distinguishes a live controversy from one
  settled decades ago. Publication dates are held; the map barely uses them.
- **Claim curation.** Claims are hand-written. Who decides what counts as a
  common claim, and how is that kept from encoding the author's priors?
- **Contradiction between claims.** Claims are judged independently, so the map
  cannot yet notice when two of its own claims disagree.
- **Publication.** Deployment target is static hosting. Unresolved: whether the
  map is presented as a finished resource or as visibly in progress — the
  honest answer today is the latter.
