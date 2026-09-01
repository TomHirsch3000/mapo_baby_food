#!/usr/bin/env python3
"""
polarity.py — BACKLOG 1c. Stance computed from reported facts, not judged.

The complement-exposure failure is not a prompt-tuning problem. On
`back_to_sleep`, of the findings that report the opposite exposure ("prone
increases risk" rather than "supine reduces it"), the stored verdicts are 9
supports and 9 refutes. Exactly half. The model is not applying a rule badly;
it is not applying a rule at all — so a better-worded instruction has nothing
to improve, and every patch that flips on "the exposure is opposite" breaks as
many rows as it fixes.

So the rule moves into Python. The model is asked only for things it can read
off the page: what THIS paper's exposure was, whether that is the same thing
the claim names or its complement, and which way the outcome moved. It is never
asked whether the paper agrees with anything, and it is never shown
`claim_sign` — with the direction hidden there is nothing to pattern-match
against, so the answer has to come from the abstract.

    implied = effect x exposure_relation
    supports  if implied == claim_sign  else  refutes

"Prone increases SIDS", against a claim signed -1 on supine:
    effect +1, relation -1  ->  implied -1  ->  matches -1  ->  supports.

The double negative becomes arithmetic, and arithmetic does not coin-flip.

Requires `claim_sign`, `claim_exposure` and `claim_outcome` on the registry
(BACKLOG 1d). A claim with no sign — a `threshold` claim — cannot be resolved
this way and is returned as None rather than guessed at.
"""

SYSTEM = (
    "You are a careful evidence analyst for paediatric research. "
    "You report what a paper measured and which way its results moved. "
    "You never decide whether a paper agrees with a claim. "
    "Respond ONLY with valid JSON, no markdown, no commentary."
)

PROMPT = """\
A claim links one thing to another. Here are its two halves:

  CLAIM EXPOSURE: {claim_exposure}
  CLAIM OUTCOME:  {claim_outcome}

PAPER TITLE: {title}
ABSTRACT: {abstract}

Report what THIS PAPER did and found. Do NOT decide whether it agrees with the
claim. You have deliberately not been told which direction the claim asserts,
because agreement is computed from your answers afterwards.

Respond with ONLY this JSON, filling the fields in order:
{{
  "paper_exposure": "<what was given to, done to, or measured about the people studied, max 12 words>",
  "exposure_relation": "same | opposite | different",
  "paper_outcome": "<what was measured as a result, max 12 words>",
  "outcome_relation": "same | different",
  "effect": "increased | decreased | no_change | unclear",
  "effect_quote": "<the sentence from the ABSTRACT reporting that result, copied WORD FOR WORD, or an empty string>",
  "confidence": <0-100 integer>,
  "study_type": "<meta-analysis | rct | cohort | case-control | cross-sectional | review | case-report | other>"
}}

"exposure_relation" — compare PAPER EXPOSURE with CLAIM EXPOSURE:
- "same"      the same thing, or a close synonym. Supine and back sleeping are
              the same. Early introduction and introduction before 6 months are
              the same.
- "opposite"  the complement of it, the other side of the same either/or.
              Prone is the opposite of supine. Delaying is the opposite of
              introducing early. Avoidance is the opposite of consumption.
              Formula feeding is the opposite of exclusive breastfeeding.
- "different" neither. A separate exposure altogether: bed-sharing is DIFFERENT
              from pacifier use, not opposite to it. If you are torn between
              "opposite" and "different", answer "different".

"effect" — did the PAPER'S OWN exposure increase or decrease the PAPER'S OWN
outcome? Report the direction this paper reports, about the exposure this paper
studied. Do not translate it onto the claim's exposure. That translation is the
arithmetic you are not doing.
- "increased"  more of the paper's exposure went with more of its outcome:
               a raised risk, a higher score, a longer duration
- "decreased"  more of the paper's exposure went with less of its outcome
- "no_change"  it looked and found no significant association
- "unclear"    the abstract reports no direction

Rules:
- Judge only from this abstract. Do not use outside knowledge.
- "outcome_relation" is "same" if the paper measured the claim's outcome or a
  standard proxy for it, "different" otherwise.
- An odds ratio or relative risk ABOVE 1 is "increased", BELOW 1 is "decreased".
- "no_change" is a real finding and is not "unclear". Use it only where the
  paper says it looked and found nothing.
- The quote is checked against the abstract afterwards and dropped if it is not
  literally present, so an invented one only loses information.

Example — the complement case:
CLAIM EXPOSURE: back (supine) sleep position
CLAIM OUTCOME: SIDS
Abstract: "Prone and side sleeping positions were associated with a markedly
increased risk of SIDS compared with supine."
{{"paper_exposure": "prone and side sleep position", "exposure_relation": "opposite", "paper_outcome": "SIDS risk", "outcome_relation": "same", "effect": "increased", "effect_quote": "Prone and side sleeping positions were associated with a markedly increased risk of SIDS compared with supine.", "confidence": 95, "study_type": "case-control"}}

Note what that example does NOT do. It does not work out what prone sleeping
implies about back sleeping. It reports prone, marks it the opposite of supine,
and reports that risk went up. That is the whole job.
"""

EXPOSURE_RELATIONS = ("same", "opposite", "different")
EFFECTS = ("increased", "decreased", "no_change", "unclear")

RELATION_SIGN = {"same": 1, "opposite": -1}
EFFECT_SIGN = {"increased": 1, "decreased": -1, "no_change": 0}


# ─────────────────────────────────────────────────────────────────────────────
# V2 — after the first version scored 29% and 14% on the complement stratum
# ─────────────────────────────────────────────────────────────────────────────
#
# The v1 run answered `opposite` ZERO times out of 57. Distribution was
# different 38, same 10, unparseable 9. The entire mechanism sat behind that one
# branch and the model never took it, so every complement paper fell through to
# `different` and resolved as neutral.
#
# The cause was a line in the v1 prompt: "If you are torn between 'opposite' and
# 'different', answer 'different'." Written as a conservative tiebreak, it is an
# escape hatch, and it was taken every single time. A category that costs nothing
# to choose will absorb every hard case.
#
# Three changes:
#   1. No tiebreak, and the question is asked directionally — "does more of what
#      the paper measured mean MORE or LESS of the claim's exposure?" — which has
#      no I-am-not-sure door in it.
#   2. It asks about the CLAIM's exposure, not the paper's. v1 asked "what did
#      this paper study?" and got the headline exposure: a bed-sharing study
#      whose abstract says "Dummy use was associated with a lower risk of SIDS"
#      came back as "co-sleeping", so the pacifier finding was never seen.
#      Papers report several exposures; only one of them is the claim's.
#   3. No verbatim quote. It cost output tokens and nothing downstream reads it;
#      16% of v1 responses were unparseable, and length is the likeliest cause.

PROMPT_V2 = """\
A claim links one thing to another. Here are its two halves:

  CLAIM EXPOSURE: {claim_exposure}
  CLAIM OUTCOME:  {claim_outcome}

PAPER TITLE: {title}
ABSTRACT: {abstract}

Your job is to find what this abstract says about CLAIM EXPOSURE and CLAIM
OUTCOME specifically — not to summarise the paper, and not to decide whether it
agrees with anything. You have deliberately not been told which direction the
claim asserts.

Respond with ONLY this JSON, filling the fields in order:
{{
  "measured": "<the thing this paper measured that bears on CLAIM EXPOSURE, max 12 words, or "" if there is none>",
  "exposure_relation": "same | opposite | different",
  "outcome_relation": "same | different",
  "effect": "increased | decreased | no_change | unclear",
  "confidence": <0-100 integer>,
  "study_type": "<meta-analysis | rct | cohort | case-control | cross-sectional | review | case-report | other>"
}}

FIRST, find the exposure. A paper often measures several things. You are looking
only for the one that bears on CLAIM EXPOSURE — even when it is not the paper's
headline finding, and even when it appears in a single sentence near the end.

THEN answer "exposure_relation" by asking: if there were MORE of what this paper
measured, would there be MORE or LESS of CLAIM EXPOSURE?
- "same"      more of it means MORE of the claim's exposure. It is the same
              thing, or a close synonym.
- "opposite"  more of it means LESS of the claim's exposure. The two are the two
              sides of one choice — an infant is put down prone or supine, fed
              formula or breastmilk, given a food early or late. Measuring one
              side measures the other.
- "different" the paper measures something that is not on that axis at all, so
              more of it tells you nothing about the claim's exposure.

Complementary pairs are COMMON in this literature — roughly a quarter of papers
report the mirror image of the exposure a claim names. Some you will meet:

  supine sleeping        <-> prone or side sleeping
  exclusive breastfeeding <-> formula feeding
  early introduction     <-> delaying or avoiding
  room-sharing           <-> sleeping alone in a separate room
  pacifier use           <-> no pacifier
  swaddled               <-> unswaddled
  more screen time       <-> less screen time

"different" means genuinely off-axis. Bed-sharing is different from pacifier use
— neither more nor less of one changes the other. Do not use "different" for a
case you find hard to call; decide it.

THEN answer "effect": did MORE of the thing this paper measured go with MORE or
LESS of the paper's outcome? Report the direction the paper reports, about the
thing the paper measured. Do not translate it onto the claim's exposure — that
translation is done afterwards and is not your job.
- "increased"  a raised risk, a higher score, an odds ratio above 1
- "decreased"  a lowered risk, a lower score, an odds ratio below 1
- "no_change"  it looked and found no significant association
- "unclear"    the abstract reports no direction

Rules:
- "outcome_relation" is "same" if the paper measured CLAIM OUTCOME or a standard
  proxy for it, "different" otherwise.
- If the abstract says nothing about CLAIM EXPOSURE or its mirror image, answer
  "measured": "", "exposure_relation": "different".
- Judge only from this abstract. Do not use outside knowledge.

Example — the complement case:
CLAIM EXPOSURE: back (supine) sleep position
CLAIM OUTCOME: SIDS
Abstract: "Prone and side sleeping positions were associated with a markedly
increased risk of SIDS compared with supine."
{{"measured": "prone and side sleep position", "exposure_relation": "opposite", "outcome_relation": "same", "effect": "increased", "confidence": 95, "study_type": "case-control"}}

More prone means less supine, so the relation is "opposite". Prone went with
more SIDS, so the effect is "increased". You are not asked what that implies
about supine sleeping, and you should not work it out.

Example — the finding is not the headline:
CLAIM EXPOSURE: pacifier use at sleep onset
CLAIM OUTCOME: SIDS
Abstract: a bed-sharing case-control study, which reports late on that "Dummy
use was associated with a lower risk of SIDS among co-sleepers."
{{"measured": "dummy (pacifier) use at sleep onset", "exposure_relation": "same", "outcome_relation": "same", "effect": "decreased", "confidence": 70, "study_type": "case-control"}}

The paper is about bed-sharing. That does not matter — it reports on pacifier
use, which is the claim's exposure, so that is what you extract.
"""


def validate_v2(data):
    """Clamp the v2 output. Same shape as validate(), minus the quote."""
    if not isinstance(data, dict):
        return None

    relation = str(data.get("exposure_relation", "")).strip().lower()
    relation = next((r for r in EXPOSURE_RELATIONS if r in relation), None)
    if relation is None:
        return None

    effect = str(data.get("effect", "")).strip().lower().replace(" ", "_")
    effect = next((e for e in EFFECTS if e in effect), None)
    if effect is None:
        return None

    out_relation = str(data.get("outcome_relation", "")).strip().lower()
    out_relation = "different" if "differ" in out_relation else "same"

    try:
        confidence = max(0, min(100, int(float(data.get("confidence", 50)))))
    except (TypeError, ValueError):
        confidence = 50

    measured = str(data.get("measured") or "").strip()[:200]
    # Nothing found on the claim's axis is the same answer as off-axis, and
    # saying so here keeps resolve() from having to know about the difference.
    if not measured:
        relation = "different"

    return {
        "paper_exposure": measured,
        "exposure_relation": relation,
        "paper_outcome": "",
        "outcome_relation": out_relation,
        "effect": effect,
        "effect_quote": "",
        "confidence": confidence,
        "study_type": str(data.get("study_type") or "other").strip().lower()[:40],
    }


def validate(data):
    """Clamp the polarity call's output. None if it cannot be used at all."""
    if not isinstance(data, dict):
        return None

    relation = str(data.get("exposure_relation", "")).strip().lower()
    relation = next((r for r in EXPOSURE_RELATIONS if r in relation), None)
    if relation is None:
        return None

    effect = str(data.get("effect", "")).strip().lower().replace(" ", "_")
    effect = next((e for e in EFFECTS if e in effect), None)
    if effect is None:
        return None

    # Only "different" needs detecting; anything else is treated as the claim's
    # own outcome, which is the case the screen has usually already established.
    out_relation = str(data.get("outcome_relation", "")).strip().lower()
    out_relation = "different" if "differ" in out_relation else "same"

    try:
        confidence = max(0, min(100, int(float(data.get("confidence", 50)))))
    except (TypeError, ValueError):
        confidence = 50

    return {
        "paper_exposure": str(data.get("paper_exposure") or "").strip()[:200],
        "exposure_relation": relation,
        "paper_outcome": str(data.get("paper_outcome") or "").strip()[:200],
        "outcome_relation": out_relation,
        "effect": effect,
        "effect_quote": str(data.get("effect_quote") or "").strip(),
        "confidence": confidence,
        "study_type": str(data.get("study_type") or "other").strip().lower()[:40],
    }


def resolve(claim_sign, reported):
    """Turn the reported facts into a verdict. No model judgement involved.

    Returns (stance, reason). The reason records WHY, so a wrong verdict can be
    traced to the field that produced it instead of to a black box — which is
    the whole advantage of computing this rather than asking for it.
    """
    if not reported:
        return None, "unparseable"

    # A paper measuring a different exposure, or a different outcome, has not
    # tested this claim. It is not evidence in either direction, and forcing it
    # into one is the relevance leakage that put a circumcision hypothesis on a
    # sleep-position claim.
    if reported["exposure_relation"] == "different":
        return "neutral", "exposure is neither the claim's nor its complement"
    if reported["outcome_relation"] == "different":
        return "neutral", "measured a different outcome"
    if reported["effect"] == "unclear":
        return "neutral", "abstract reports no direction"
    if reported["effect"] == "no_change":
        return "neutral", "tested and found no association"

    if claim_sign not in (1, -1):
        # A threshold claim has no direction to agree with. Guessing one here is
        # exactly how a confident number gets attached to a question nobody
        # asked, so it declines instead.
        return None, "claim has no sign (threshold claim)"

    implied = EFFECT_SIGN[reported["effect"]] * RELATION_SIGN[reported["exposure_relation"]]
    stance = "supports" if implied == claim_sign else "refutes"
    return stance, (f"{reported['effect']} x {reported['exposure_relation']} "
                    f"-> implied {implied:+d}, claim {claim_sign:+d}")
