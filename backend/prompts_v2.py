#!/usr/bin/env python3
"""
prompts_v2.py — Prompts for the relevance restructure.

Wired into `bakeoff.py` as the `decomposed` candidate, so it can be measured
against the one-call prompt. NOT yet wired into the live pipeline: nothing here
writes to claims.db, and SCREEN_COLUMNS below is still a proposal rather than
applied schema. Measure first, migrate second.

The current evaluator asks one question: "does this paper support the claim?"
Everything that is not a supports/refutes/mixed answer falls into `neutral`,
which is therefore three different things wearing one badge:

    - a paper that tests the claim and found nothing
    - a paper that tests something ADJACENT to the claim
    - a paper that is in the corpus by retrieval accident

31% of the corpus (2,435 of 7,769 pairs) is currently in that bucket, and the
evidence view's "context box" is filled from it by citation count alone — so a
paper ends up there for failing a test, not for passing one.

The restructure splits the single question in two, in the order a reader would
ask them:

    SCREEN   what did this paper measure, and how close is that to the claim?
    STANCE   given that it does bear on the claim, which way does it point?

Screening is cheap and gates the expensive call: ~30% of pairs never reach the
stance prompt at all, which roughly pays for the second call. It also gives a
small model one job at a time, which is the only way a 7B model does either job
well.

Every field the model is asked for is either shown to the reader or used in the
geometry. Nothing here is extracted "in case it is useful later" — the binding
constraint is hours of local inference per pass, so the pass has to collect
everything the map needs in one go.
"""

# ─────────────────────────────────────────────────────────────────────────────
# CALL 1 — SCREEN
# ─────────────────────────────────────────────────────────────────────────────

SCREEN_SYSTEM = (
    "You are a careful evidence analyst for paediatric research. "
    "You describe what a paper measured before you judge how relevant it is. "
    "Respond ONLY with valid JSON, no markdown, no commentary."
)

# The three PICO fields come FIRST for the same reason `finding` comes first in
# the stance prompt: the model generates left to right, so making it write down
# WHO was studied, WHAT was done to them and WHAT was measured before it commits
# to a tier stops it from scoring topic-similarity as relevance. Without this, a
# 7B model marks any abstract containing the word "peanut" as directly testing
# early peanut introduction.
SCREEN_PROMPT = """\
CLAIM (as a study could test it): "{tested}"
THE CLAIM IS ABOUT: {population}

PAPER TITLE: {title}
ABSTRACT: {abstract}

First describe what this paper measured. Then decide how closely that bears on
the CLAIM.

Respond with ONLY this JSON, filling the fields in order:
{{
  "population": "<who was studied, max 12 words; '(not stated)' if the abstract does not say>",
  "age_min_months": <integer or null>,
  "age_max_months": <integer or null>,
  "age_basis": "stated | inferred | unknown",
  "age_quote": "<the exact phrase from the abstract that gave those ages, or ''>",
  "exposure": "<what was given to them, done to them, or measured about them, max 12 words>",
  "outcome": "<what was measured as a result, max 12 words>",
  "overlap": "<compared with the CLAIM, is that the same question, a related one, or a different one? answer 'same', 'related', or 'different'>",
  "relevance": "direct | indirect | framework | background",
  "offers": "<method | measure | definition | mechanism | guideline | ''>",
  "relevance_reason": "<one sentence, max 20 words, on why it lands in that tier>"
}}

The tiers, in order — take the FIRST one that fits:

- "direct"     The paper tests the claim. The population, the exposure and the
               outcome are all the ones the claim is about. Answer this whether
               the paper agrees with the claim or flatly contradicts it.
- "indirect"   The paper tests a neighbouring question that still informs the
               claim: an older population, an animal model, a proxy outcome, a
               related exposure, a different dose or route. Informative about
               the direction, not decisive about the claim.
- "framework"  The paper does NOT test the claim, but supplies something the
               papers that do test it would use: a measurement instrument, a
               definition, a mechanism, a guideline, or a modelling approach.
               You MUST name which in "offers".
- "background" Everything else. Mentions the topic but neither tests the claim
               nor gives anyone a tool for testing it — commentary, an unrelated
               outcome, a review of a different question, a passing mention.

Rules:
- Relevance is about WHAT WAS MEASURED, never about whether the findings agree.
  A paper whose results destroy the claim is "direct". Disagreement is the next
  question, not this one.
- "framework" must be earned. If you cannot name what it offers in one word,
  it is "background".
- Ages are in MONTHS. Convert weeks (divide by 4.35) and years (multiply by 12).
- Report the age at which the EXPOSURE happened, not the age at follow-up. A
  study giving peanut at 5 months and testing allergy at 5 years is 5 to 5, not
  5 to 60.
- If only one age is given, use it for both min and max.
- If the abstract gives no age at all, both ages are null and age_basis is
  "unknown". Do NOT infer an age from the topic — "infant" is not a number.
  Use "inferred" only when the abstract gives a life stage precise enough to
  bound it, such as "neonates" or "preschoolers", and say so in age_quote.
- Judge only from this abstract. Do not use outside knowledge.

Example — DIRECT, and disagreeing:
CLAIM: "Introducing peanut before 12 months reduces the risk of peanut allergy"
Abstract: "In 640 infants at high risk, randomised at 4-11 months to peanut
consumption or avoidance, allergy at 60 months was 13.7% vs 1.9%."
{{"population": "high-risk infants", "age_min_months": 4, "age_max_months": 11, "age_basis": "stated", "age_quote": "randomised at 4-11 months", "exposure": "peanut consumption versus avoidance", "outcome": "peanut allergy at age five", "overlap": "same", "relevance": "direct", "offers": "", "relevance_reason": "Randomises the exact exposure in the claim's population and measures the claim's outcome."}}

Example — INDIRECT:
CLAIM: "Introducing peanut before 12 months reduces the risk of peanut allergy"
Abstract: "Early introduction of cooked egg at 6 months reduced egg allergy at
12 months in a randomised trial of 820 infants."
{{"population": "infants", "age_min_months": 6, "age_max_months": 6, "age_basis": "stated", "age_quote": "cooked egg at 6 months", "exposure": "early cooked egg introduction", "outcome": "egg allergy at twelve months", "overlap": "related", "relevance": "indirect", "offers": "", "relevance_reason": "Same early-introduction principle and age window, but a different allergen."}}

Example — FRAMEWORK:
CLAIM: "Introducing peanut before 12 months reduces the risk of peanut allergy"
Abstract: "We describe a standardised double-blind placebo-controlled food
challenge protocol for diagnosing food allergy in children under two."
{{"population": "children under two", "age_min_months": 0, "age_max_months": 24, "age_basis": "stated", "age_quote": "children under two", "exposure": "diagnostic food challenge protocol", "outcome": "none - method paper", "overlap": "different", "relevance": "framework", "offers": "method", "relevance_reason": "Defines the challenge protocol the trials use to decide whether a child is allergic."}}

Example — BACKGROUND:
CLAIM: "Introducing peanut before 12 months reduces the risk of peanut allergy"
Abstract: "We surveyed 300 restaurant managers on allergen labelling practices
and found inconsistent compliance."
{{"population": "restaurant managers", "age_min_months": null, "age_max_months": null, "age_basis": "unknown", "age_quote": "", "exposure": "allergen labelling practice", "outcome": "compliance rate", "overlap": "different", "relevance": "background", "offers": "", "relevance_reason": "About catering compliance, not about whether early introduction prevents allergy."}}
"""


# ─────────────────────────────────────────────────────────────────────────────
# CALL 2 — STANCE  (only for relevance in {direct, indirect})
# ─────────────────────────────────────────────────────────────────────────────

STANCE_SYSTEM = (
    "You are a careful evidence analyst for paediatric research. "
    "You judge only what the abstract actually shows. "
    "Respond ONLY with valid JSON, no markdown, no commentary."
)

# Deliberately close to the prompt it replaces. That prompt is tuned, the
# finding-before-stance ordering is the thing that makes it work, and a full
# re-run is hours — so the only changes here are the ones the restructure
# forces. Two of them:
#
#   1. The screen has already established that this paper bears on the claim, and
#      says how. That is fed back in, so the model is not re-deciding relevance
#      inside a question about direction.
#   2. "neutral" survives, but its meaning narrows to "tests the claim and found
#      nothing conclusive". It is no longer the drain for everything unmatched,
#      because background papers never reach this prompt.
STANCE_PROMPT = """\
CLAIM: "{tested}"

PAPER TITLE: {title}
ABSTRACT: {abstract}

This paper has already been established to bear on the claim: it {relevance_line}
It measured: {exposure} -> {outcome}, in {population}.

Decide whether its findings SUPPORT or REFUTE the CLAIM.

Respond with ONLY this JSON, filling the fields in order:
{{
  "finding": "<what the paper actually concluded, in your own words, max 20 words>",
  "direction": "<does that conclusion agree or disagree with the CLAIM? answer 'agrees', 'disagrees', 'both', or 'inconclusive'>",
  "stance": "supports | refutes | neutral | mixed",
  "confidence": <0-100 integer>,
  "summary": "<one sentence, max 25 words, on what this paper found about the claim>",
  "study_type": "<meta-analysis | rct | cohort | case-control | cross-sectional | review | case-report | other>"
}}

Rules:
- "agrees"       -> stance "supports"
- "disagrees"    -> stance "refutes"
- "both"         -> stance "mixed"
- "inconclusive" -> stance "neutral", with confidence below 50
- Answer "both" when the abstract reports findings pointing BOTH ways on this
  claim - for example harm at a large dose alongside benefit at a small one. Do
  not average them into one direction and do not pick the louder result. If you
  answer "both", the summary MUST state both sides.
- Read negations carefully. "no association", "was not a risk factor", "no
  significant difference", "did not reduce" mean the paper DISAGREES with a
  claim that asserts an effect. Matching keywords is NOT agreement.
- "inconclusive" is for a paper that set out to test this and could not tell -
  underpowered, null with wide intervals, or explicitly calling for more work.
  It is NOT for a paper about something else; those never reach this question.
- A paper judged "indirect" still takes a direction. Report the direction its
  evidence points, and let the lower confidence carry the distance from the
  claim.
- study_type is the DESIGN, not how good you think the paper is.
- Judge only from this abstract. Do not use outside knowledge.

Example of a MIXED paper:
CLAIM: "Screen media should be avoided before 18-24 months"
Abstract concludes: "More screen time was associated with poorer language, but educational programming and co-viewing were associated with better language."
{{"finding": "Quantity of screen use harmed language; quality of screen use helped it", "direction": "both", "stance": "mixed", "confidence": 85, "summary": "More screen time tracked worse language, but educational and co-viewed content tracked better language.", "study_type": "meta-analysis"}}

Example of a REFUTING paper:
CLAIM: "Vitamin C prevents the common cold"
Abstract concludes: "Regular vitamin C supplementation had no effect on common cold incidence."
{{"finding": "Vitamin C supplementation did not reduce cold incidence", "direction": "disagrees", "stance": "refutes", "confidence": 90, "summary": "Found no effect of vitamin C on cold incidence.", "study_type": "meta-analysis"}}
"""

# What gets substituted into {relevance_line}, so the sentence reads naturally
# and the model is told the tier as a fact rather than as a label to re-litigate.
RELEVANCE_LINE = {
    "direct": "tests this exact question.",
    "indirect": "tests a closely related question, so its findings inform the "
                "claim without settling it.",
}

# Tiers that reach the stance prompt at all. `framework` and `background` are
# recorded by the screen and never evaluated - which is the point: they cost
# nothing, and nothing they might have said can leak into the verdict.
SCORED_TIERS = ("direct", "indirect")

RELEVANCE_TIERS = ("direct", "indirect", "framework", "background")
OFFERS = ("method", "measure", "definition", "mechanism", "guideline")


# ─────────────────────────────────────────────────────────────────────────────
# Schema this pass needs on claim_papers
# ─────────────────────────────────────────────────────────────────────────────
#
# All per-PAIR, not per-paper: the same paper is direct evidence for one claim
# and background for another, and the age window that matters is the one the
# claim asks about.
SCREEN_COLUMNS = [
    ("relevance",        "TEXT"),     # direct | indirect | framework | background
    ("relevance_reason", "TEXT"),     # shown to the reader, per Principle 4
    ("offers",           "TEXT"),     # framework papers only
    ("population",       "TEXT"),
    ("exposure",         "TEXT"),
    ("outcome",          "TEXT"),
    ("overlap",          "TEXT"),     # same | related | different
    ("age_min_months",   "INTEGER"),
    ("age_max_months",   "INTEGER"),
    ("age_basis",        "TEXT"),     # stated | inferred | unknown
    ("age_quote",        "TEXT"),     # the phrase the ages came from
    ("screened_at",      "TEXT"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Validators
# ─────────────────────────────────────────────────────────────────────────────
#
# Same contract as evaluate_claims.validate: clamp the model's output into the
# shape the rest of the code expects, or return None if it cannot be used at
# all. None is a real result and must not be retried away — a model that cannot
# hold the output format is worse at the job, and hiding that flatters it.

STANCES = ("supports", "refutes", "neutral", "mixed")
AGE_BASES = ("stated", "inferred", "unknown")
OVERLAPS = ("same", "related", "different")

MAX_AGE_MONTHS = 1200          # 100 years; anything beyond is a parse artefact


def _months(value):
    """An age in months, or None. Rejects the out-of-range numbers a model
    produces when it reports years in a field labelled months."""
    try:
        n = int(float(value))
    except (TypeError, ValueError):
        return None
    return n if 0 <= n <= MAX_AGE_MONTHS else None


def validate_screen(data):
    """Clamp the SCREEN call's output. None if the tier is unreadable."""
    if not isinstance(data, dict):
        return None

    # Loose substring match, like the stance validator, because models pad the
    # answer: "directly tests it", "mostly background".
    raw = str(data.get("relevance", "")).strip().lower()
    relevance = next((t for t in RELEVANCE_TIERS if t in raw), None)
    if relevance is None:
        return None

    offers = str(data.get("offers") or "").strip().lower()
    offers = next((o for o in OFFERS if o in offers), "")

    # The prompt says `framework` MUST name what it offers. A framework verdict
    # naming nothing is exactly the failure the rubric warns about — the tier
    # used as a bin for "interesting but does not fit" — so it is demoted here
    # rather than kept as a framework with a blank beside it.
    if relevance == "framework" and not offers:
        relevance = "background"

    age_min = _months(data.get("age_min_months"))
    age_max = _months(data.get("age_max_months"))
    if age_min is not None and age_max is not None and age_min > age_max:
        age_min, age_max = age_max, age_min

    basis = str(data.get("age_basis") or "").strip().lower()
    basis = next((b for b in AGE_BASES if b in basis), "unknown")
    # A basis of "stated" with no age is the model agreeing with the field label
    # rather than reporting a reading, so the absent age wins.
    if age_min is None and age_max is None:
        basis = "unknown"

    overlap = str(data.get("overlap") or "").strip().lower()
    overlap = next((o for o in OVERLAPS if o in overlap), "")

    return {
        "relevance": relevance,
        "relevance_reason": str(data.get("relevance_reason") or "").strip()[:400],
        "offers": offers,
        "population": str(data.get("population") or "").strip()[:200],
        "exposure": str(data.get("exposure") or "").strip()[:200],
        "outcome": str(data.get("outcome") or "").strip()[:200],
        "overlap": overlap,
        "age_min_months": age_min,
        "age_max_months": age_max,
        "age_basis": basis,
        "age_quote": str(data.get("age_quote") or "").strip()[:300],
    }


def validate_stance(data):
    """Clamp the STANCE call's output.

    Mirrors evaluate_claims.validate, with one difference: `mixed` is a stance
    here rather than a value of evidence_strength, because the screen has
    already removed the papers that were making `neutral` mean three things.
    """
    if not isinstance(data, dict):
        return None

    stance = str(data.get("stance", "")).strip().lower()
    stance = next((s for s in STANCES if s in stance), None)

    # Same reasoning as the one-call evaluator: `direction` is written first,
    # after the model has restated the finding, so it is the more considered
    # answer and wins when the two disagree.
    direction = str(data.get("direction", "")).strip().lower()
    if "both" in direction:              # first: "agrees with both" is mixed
        stance = "mixed"
    elif "disagree" in direction:
        stance = "refutes"
    elif "inconclusive" in direction:
        stance = "neutral"
    elif "agree" in direction:           # after "disagree", so a real agree
        stance = "supports"
    if stance is None:
        return None

    try:
        confidence = max(0, min(100, int(float(data.get("confidence", 50)))))
    except (TypeError, ValueError):
        confidence = 50
    if stance == "neutral":
        confidence = min(confidence, 49)   # the prompt asks for below 50

    return {
        "stance": stance,
        "confidence": confidence,
        "stance_summary": str(data.get("summary") or "").strip()[:400],
        "study_type": str(data.get("study_type") or "other").strip().lower()[:40],
        "finding": str(data.get("finding") or "").strip()[:400],
        "direction": direction[:60],
    }
