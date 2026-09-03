#!/usr/bin/env python3
"""
extract.py — Read a paper ONCE, without ever showing it a claim. Match in Python.

Every other candidate hands the model a claim and asks it to judge a paper
against it. This one does not mention the claim at all. The model is asked only
what the paper studied, in whom, and which way the result went. The comparison
to a claim happens afterwards, in code, against the registry fields 1d filled in.

Three consequences, and the first is the reason to care:

**Extraction is per PAPER, judgement is per PAIR.** The corpus holds 6,672
papers across 7,769 pairs, so a paper studied for two claims is currently read
twice and will be read again for a third. Extracted once, it is reusable for
every claim that ever exists - including claims not written yet. Adding a claim
stops costing inference at all, which is most of what makes BACKLOG 19 hard.

**The model cannot pattern-match to a claim it has not seen.** The failure this
whole project is chasing - "bed-sharing increases SIDS" scored as supporting a
pacifier claim because every keyword matched - is not available to it. It has
nothing to match against.

**Validation decomposes.** Checking "does this abstract support this claim" means
reading the abstract and holding the claim in your head. Checking "did this paper
measure prone sleeping in infants under 12 months, and did the risk go up" is
four small factual questions, each answerable by ctrl-F. A human or a second
model can audit the extraction without adjudicating the claim, and audit the
matching without reading a paper.

The cost is that matching becomes the hard part, and it is not free: "prone
sleeping" has to be recognised as the complement of "placing infants on their
back to sleep". That is what `keyword_hints` and `claim_exposure` are for, and
where this design will succeed or fail.
"""

import re

SYSTEM = (
    "You are a careful research assistant. You read a paediatric research "
    "abstract and report what it studied, in whom, and what it found. "
    "You are never asked whether it agrees with anything. "
    "Respond ONLY with valid JSON, no markdown, no commentary."
)

PROMPT = """\
PAPER TITLE: {title}
ABSTRACT: {abstract}

Report what this paper studied and found. There is no claim to compare it to and
no verdict to reach - you are building a record of the paper itself.

Respond with ONLY this JSON, filling the fields in order:
{{
  "population": "<who was studied, max 10 words; '' if the abstract does not say>",
  "age_min_months": <integer or null>,
  "age_max_months": <integer or null>,
  "exposure": "<what was given to them, done to them, or measured about them, max 10 words>",
  "comparator": "<what it was compared against, max 10 words, or '' if none>",
  "outcome": "<what was measured as a result, max 10 words>",
  "effect": "increased | decreased | no_change | unclear",
  "effect_size": "<the headline number as written - an odds ratio, a percentage, a mean difference - or ''>",
  "study_type": "<meta-analysis | rct | cohort | case-control | cross-sectional | review | case-report | other>"
}}

"exposure" is the thing whose effect was being studied. Name it as the paper
names it - if the paper studied prone sleeping, write "prone sleeping", not
"sleep position" and not "supine sleeping". The exact wording is what the
matching depends on.

"effect" is the direction between THIS paper's exposure and THIS paper's
outcome:
- "increased"  more exposure went with more outcome - a raised risk, a higher
               score, an odds ratio above 1
- "decreased"  more exposure went with less outcome - an odds ratio below 1
- "no_change"  it looked and found no significant association
- "unclear"    the abstract reports no direction, or the paper measured nothing
               (a guideline, a commentary, a protocol)

Ages are in MONTHS. Convert weeks (divide by 4.35) and years (multiply by 12).
Report the age at which the EXPOSURE happened, not the age at follow-up: a study
giving peanut at 5 months and testing allergy at 5 years is 5 to 5, not 5 to 60.
If only one age is given use it for both. If the abstract gives no age, both are
null - do NOT infer an age from the topic, "infant" is not a number.

Judge only from this abstract. Do not use outside knowledge. If the paper is not
a study - a guideline, an editorial, a review of other work - say so through
`study_type` and set `effect` to "unclear".

Example:
Abstract: "In a case-control study of 400 SIDS cases and 1,386 controls, prone
and side sleeping were associated with a markedly increased risk of SIDS
compared with supine (OR 3.9, 95% CI 2.7-5.6) among infants under one year."
{{"population": "infants under one year", "age_min_months": 0, "age_max_months": 12, "exposure": "prone and side sleeping", "comparator": "supine sleeping", "outcome": "SIDS risk", "effect": "increased", "effect_size": "OR 3.9 (95% CI 2.7-5.6)", "study_type": "case-control"}}
"""

EFFECTS = ("increased", "decreased", "no_change", "unclear")
MAX_AGE_MONTHS = 1200


def _months(value):
    try:
        n = int(float(value))
    except (TypeError, ValueError):
        return None
    return n if 0 <= n <= MAX_AGE_MONTHS else None


def validate(data):
    """Clamp an extraction. None only if the effect is unreadable."""
    if not isinstance(data, dict):
        return None
    effect = str(data.get("effect", "")).strip().lower().replace(" ", "_")
    effect = next((e for e in EFFECTS if e in effect), None)
    if effect is None:
        return None

    lo, hi = _months(data.get("age_min_months")), _months(data.get("age_max_months"))
    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo

    return {
        "population": str(data.get("population") or "").strip()[:200],
        "age_min_months": lo,
        "age_max_months": hi,
        "exposure": str(data.get("exposure") or "").strip()[:200],
        "comparator": str(data.get("comparator") or "").strip()[:200],
        "outcome": str(data.get("outcome") or "").strip()[:200],
        "effect": effect,
        "effect_size": str(data.get("effect_size") or "").strip()[:120],
        "study_type": str(data.get("study_type") or "other").strip().lower()[:40],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Matching — no model involved past this point
# ─────────────────────────────────────────────────────────────────────────────
#
# Complementary pairs. The whole design turns on recognising that a paper about
# prone sleeping bears on a claim about supine sleeping, in the opposite
# direction. These are the axes the corpus actually contains; a pair not listed
# here reads as "different exposure" and the paper does not vote, which is the
# safe failure.
COMPLEMENTS = [
    ({"supine", "back to sleep", "back sleeping", "non-prone", "nonprone"},
     {"prone", "front sleeping", "stomach", "side sleeping"}),
    ({"breastfeed", "breast milk", "breast-fed", "human milk"},
     {"formula", "bottle-fed", "bottle feeding"}),
    ({"early introduction", "introducing early", "before 6 months", "before 12 months",
      "early exposure", "consumption"},
     {"delay", "avoidance", "avoiding", "withholding", "later introduction"}),
    ({"room-sharing", "room sharing"}, {"separate room", "solitary sleep"}),
    ({"pacifier", "dummy", "soother"}, {"no pacifier", "without a pacifier"}),
    ({"swaddl"}, {"unswaddled", "not swaddled"}),
    ({"tummy time", "prone play", "awake prone"}, {"no tummy time", "supine play"}),
]

WORD = re.compile(r"[a-z0-9]+")


def _norm(text):
    return " ".join(WORD.findall((text or "").lower()))


def _mentions(haystack, needles):
    h = _norm(haystack)
    return any(_norm(n) in h for n in needles)


def exposure_relation(paper_exposure, paper_comparator, claim_exposure, hints):
    """same | opposite | different — decided in code, not by a model."""
    pe, ce = _norm(paper_exposure), _norm(claim_exposure)
    if not pe or not ce:
        return "different"

    # Complements are tested FIRST, because they are the specific case and word
    # overlap is the general one. "delayed peanut introduction" and "introducing
    # peanut before 6 months" share `peanut` and `introduction`, so an overlap
    # test run first calls them the same thing and inverts the verdict - which
    # is the exact failure this whole design exists to remove, reintroduced in
    # the matcher instead of the model.
    for side_a, side_b in COMPLEMENTS:
        a_claim, b_claim = _mentions(ce, side_a), _mentions(ce, side_b)
        a_paper, b_paper = _mentions(pe, side_a), _mentions(pe, side_b)
        if (a_claim and b_paper) or (b_claim and a_paper):
            return "opposite"
        if (a_claim and a_paper) or (b_claim and b_paper):
            return "same"

    # Direct overlap of content words, ignoring the filler a claim carries
    # ("placing infants on their back to sleep" vs "back sleeping").
    STOP = {"the", "a", "an", "of", "in", "on", "to", "for", "and", "or", "at",
            "their", "with", "infants", "infant", "babies", "baby", "children"}
    pw = {w for w in pe.split() if w not in STOP}
    cw = {w for w in ce.split() if w not in STOP}
    if pw & cw:
        return "same"

    # A comparator can carry the match: a trial of "peanut consumption vs
    # avoidance" names the claim's exposure on whichever side it sits.
    if paper_comparator and _norm(paper_comparator):
        cmp_w = {w for w in _norm(paper_comparator).split() if w not in STOP}
        if cmp_w & cw:
            return "opposite"

    if hints and _mentions(pe, hints) and _mentions(ce, hints):
        return "same"
    return "different"


# An outcome carries a direction of its own, and missing it inverts a verdict.
# "Formula feeding increased infections" against "breastfeeding leads to BETTER
# health outcomes": the exposure is the complement AND the outcome is the
# complement, and two flips cancel. Model only the exposure and the paper comes
# out refuting a claim it supports.
#
# BACKLOG 1c named all three terms - effect, exposure_polarity, outcome_polarity
# - and this is what the third one is for.
# Prefix-matched on purpose: `infection` must catch `infections`, `death` must
# catch `deaths`, `allerg` must catch `allergy` and `allergic`. An exact word
# boundary on the right silently failed every plural, which is how "formula
# feeding increased infections" came back reading 0 valence and inverted.
GOOD_OUTCOME = re.compile(
    r"\b(better|improv|higher quality|greater|protect|benefit|adequa|sufficien"
    r"|health|develop|vocabular|literac|acceptance|self.regulation|motor skill"
    r"|retention|consolidat)", re.I)
BAD_OUTCOME = re.compile(
    r"\b(risk|death|mortalit|sids|allerg|infection|botulism|anaemia|anemia"
    r"|deficien|delay|obes|bmi|chok|injur|harm\b|poorer|worse|inadequa"
    r"|impair|disease|bleed|caries|myopia|problem|difficult|waking|eczema"
    r"|asthma|plagiocephaly|arsenic)", re.I)


def outcome_valence(text):
    """+1 if more of this outcome is a GOOD thing, -1 if bad, 0 if unreadable.

    Deliberately crude. It only has to agree with itself across the two strings
    being compared - an outcome pair it cannot read returns 0 and the paper does
    not vote, which is the safe failure.
    """
    t = text or ""
    bad, good = bool(BAD_OUTCOME.search(t)), bool(GOOD_OUTCOME.search(t))
    if bad and not good:
        return -1
    if good and not bad:
        return 1
    return 0


def outcome_matches(paper_outcome, claim_outcome, hints):
    po, co = _norm(paper_outcome), _norm(claim_outcome)
    if not po or not co:
        return False
    STOP = {"the", "a", "an", "of", "risk", "rate", "in", "and", "or", "outcomes",
            "outcome", "better", "worse", "poorer", "higher", "lower"}
    pw = {w for w in po.split() if w not in STOP}
    cw = {w for w in co.split() if w not in STOP}
    if pw & cw:
        return True
    return bool(hints) and _mentions(po, hints) and _mentions(co, hints)


RELATION_SIGN = {"same": 1, "opposite": -1}
EFFECT_SIGN = {"increased": 1, "decreased": -1, "no_change": 0}


def resolve(claim, extracted):
    """(stance, reason) from an extraction and a registry claim. No model."""
    if not extracted:
        return None, "unparseable"
    sign = claim.get("claim_sign")
    if sign not in (1, -1):
        return None, "claim has no sign (threshold claim)"

    hints = claim.get("keyword_hints") or []
    rel = exposure_relation(extracted["exposure"], extracted["comparator"],
                            claim.get("claim_exposure", ""), hints)
    if rel == "different":
        return "neutral", f"exposure {extracted['exposure']!r} not on the claim's axis"
    if not outcome_matches(extracted["outcome"], claim.get("claim_outcome", ""), hints):
        return "neutral", f"outcome {extracted['outcome']!r} is not the claim's"
    if extracted["effect"] == "unclear":
        return "neutral", "no direction reported"
    if extracted["effect"] == "no_change":
        return "neutral", "tested and found no association"

    # Three terms, not two. A paper measuring the complement exposure against
    # the complement outcome agrees with the claim: both flips cancel.
    pv = outcome_valence(extracted["outcome"])
    cv = outcome_valence(claim.get("claim_outcome", ""))
    outcome_rel = 1 if (pv == 0 or cv == 0) else (1 if pv == cv else -1)

    implied = EFFECT_SIGN[extracted["effect"]] * RELATION_SIGN[rel] * outcome_rel
    stance = "supports" if implied == sign else "refutes"
    return stance, (f"{extracted['effect']} x exposure {rel} x outcome "
                    f"{'same' if outcome_rel == 1 else 'opposite'} -> implied "
                    f"{implied:+d}, claim {sign:+d}")
