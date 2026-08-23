#!/usr/bin/env python3
"""
design.py — Canonical study design, and how far right it belongs.

The horizontal axis is meant to say "how good are the studies". It was driven by
the model's `evidence_strength` label, which turned out to be the wrong input for
two reasons.

First, the prompt defines that label by design AND size at once - "strong =
meta-analysis/large RCT; moderate = smaller RCT or prospective cohort" - so a
perfectly good but modest RCT is scored "moderate" and lands dead centre. That is
what a reader notices first.

Second, and worse, the resulting order was not an evidence hierarchy at all.
Measured over 3,700 judged papers, mean X position came out as:

    position paper              1.00
    report                      1.00
    meta-analysis               0.93
    rct                         0.89
    case-report                 0.74
    cross-sectional             0.71
    cohort                      0.69
    randomized controlled trial 0.66     <- spelled out instead of "rct"
    narrative review            0.50

Position papers above meta-analyses; case reports above cohorts; cross-sectional
above cohort; and an RCT ranked below a case report purely because the model
wrote the design out in full instead of abbreviating it. The model also invented
154 distinct study_type strings, with RCTs spread over twenty spellings.

So design is derived here instead: normalise whatever the model wrote into a
canonical design, and rank that on a conventional evidence hierarchy. The model
is still doing the reading - it is good at spotting that a paper randomised
people - it just no longer decides what that is worth.

This needs no re-evaluation: study_type is already stored for every judged pair.
"""

import re

# Ordered. First pattern that matches wins, so the specific cases - a protocol
# for an RCT, a systematic review rather than a narrative one - must precede the
# general ones they contain.
RULES = [
    # No results yet. A protocol for a trial is not the trial.
    (r"\bprotocol\b|\bplanned\b|study design paper", "protocol", 0.08),

    # Both of these must precede the opinion rule, whose \breport\b also matches
    # "case-report" across the hyphen and swallowed 88 case reports. And
    # case-control must precede case-report, or it gets read as one.
    (r"case.?control|case.?crossover", "case-control", 0.40),
    (r"case.?(report|series|study)|chart review", "case report", 0.20),

    # Opinion and synthesis-of-opinion. Authoritative, but not a study - and
    # often the very source a claim was written from, so treating it as evidence
    # for that claim would be close to circular.
    (r"position (paper|statement)|consensus|guideline|clinical practice|"
     r"commentary|editorial|perspective|narrative review|expert|"
     r"\breport\b|\bstatement\b|theor|opinion", "opinion or guidance", 0.12),

    # Not human evidence for a claim about human infants.
    (r"animal|in vivo|in.?vitro|mouse|mice|\brat\b|rodent|piglet|cell",
     "animal or lab", 0.14),
    (r"simulat|model(l)?ing|computer|machine.?learning|cost.?effective|"
     r"economic evaluation|geospatial", "modelling", 0.18),

    # Top of the hierarchy: synthesis of primary studies.
    (r"scoping review|integrative overview", "scoping review", 0.66),
    (r"meta.?anal|systematic review|systematic anal|pooled|umbrella|"
     r"cochrane", "meta-analysis", 1.00),

    # Randomised anything.
    (r"random|\brct\b", "randomised trial", 0.88),

    # Controlled or interventional but not randomised.
    (r"quasi.?experiment|controlled (study|trial)|intervention|crossover|"
     r"cross.?over|clinical trial|\btrial\b|experiment|proof of concept|"
     r"replication|field study|psychophysical|\berp\b|\bmri\b|lab.?study",
     "controlled trial", 0.72),

    # Longitudinal observation.
    (r"prospective.*cohort|cohort.*prospective|prospective longitudinal|"
     r"longitudinal cohort", "prospective cohort", 0.60),
    (r"longitudinal|follow.?up|ambispective|prospective", "longitudinal", 0.56),
    (r"retrospective", "retrospective", 0.46),
    (r"cohort", "cohort", 0.50),

    # Snapshot observation.
    (r"cross.?section|survey|questionnaire|observational|ecological|"
     r"epidemiolog|population.?based|surveillance|prevalence|"
     r"descriptive|ambulatory assessment", "cross-sectional", 0.30),

    # Secondary work on someone else's data, design unstated.
    (r"secondary (analysis|data)|pooled analysis", "secondary analysis", 0.44),

    (r"qualitative", "qualitative", 0.22),
    (r"\bpilot\b", "pilot study", 0.34),
    (r"review", "review", 0.24),          # after systematic/narrative above
]

# Unrecognised or unstated. Mid-low rather than middle: an unnamed design is more
# often a weak one, and parking unknowns dead centre would put them exactly where
# a genuinely contested-quality claim should sit.
UNKNOWN = ("unclassified", 0.30)

_COMPILED = [(re.compile(p, re.I), name, rank) for p, name, rank in RULES]


def classify(study_type):
    """Free text from the model -> (canonical design, rank 0..1)."""
    if not study_type:
        return UNKNOWN
    text = str(study_type).strip().lower()
    if not text or text in {"other", "?", "n/a", "none", "unknown"}:
        return UNKNOWN
    for pattern, name, rank in _COMPILED:
        if pattern.search(text):
            return name, rank
    return UNKNOWN


def design_of(study_type):
    return classify(study_type)[0]


def rank_of(study_type):
    return classify(study_type)[1]


# The ladder, for anything that needs to render or document it.
LADDER = [
    ("meta-analysis", 1.00),
    ("randomised trial", 0.88),
    ("controlled trial", 0.72),
    ("scoping review", 0.66),
    ("prospective cohort", 0.60),
    ("longitudinal", 0.56),
    ("cohort", 0.50),
    ("retrospective", 0.46),
    ("secondary analysis", 0.44),
    ("case-control", 0.40),
    ("pilot study", 0.34),
    ("cross-sectional", 0.30),
    ("unclassified", 0.30),
    ("review", 0.24),
    ("qualitative", 0.22),
    ("case report", 0.20),
    ("modelling", 0.18),
    ("animal or lab", 0.14),
    ("opinion or guidance", 0.12),
    ("protocol", 0.08),
]

if __name__ == "__main__":
    import sqlite3
    import os
    from collections import Counter

    db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "claims.db")
    conn = sqlite3.connect(os.path.normpath(db))
    rows = conn.execute(
        "SELECT study_type, COUNT(*) FROM claim_papers "
        "WHERE stance IS NOT NULL AND stance != '' GROUP BY 1").fetchall()

    tally = Counter()
    for st, n in rows:
        tally[classify(st)] += n

    total = sum(tally.values())
    print(f"{total} judged pairs mapped onto the design ladder:\n")
    for (name, rank), n in sorted(tally.items(), key=lambda kv: -kv[0][1]):
        bar = "#" * max(1, round(40 * n / total))
        print(f"  {rank:.2f}  {name:20} {n:5}  {bar}")

    unknown = tally[UNKNOWN]
    print(f"\nunclassified: {unknown} ({100 * unknown / total:.1f}%)")
