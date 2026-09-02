#!/usr/bin/env python3
"""
build_claims_data.py — Export claims.db into the static JSON the frontend reads.

One file per screen:

    public/claims/topics.json                   landing page (topic nodes)
    public/claims/<topic>/claims.json           claim nodes for one topic
    public/claims/<topic>/<claim>/evidence.json papers, split by stance

Node SIZE on both screens comes from OpenAlex match counts, not from collected
papers, so a claim nobody has researched yet still appears at its true size.
That deliberately decouples "how much literature exists around these keywords"
from "how much evidence we actually hold" — the gap between the two is the
interesting signal, and the UI shows both numbers.

Claim node POSITION still comes from the evidence we do hold:

    netSupport   -1 (refuted) .. +1 (supported); drives Y POSITION
    consensus    |netSupport|; 0 = contested, 1 = settled
    evidenceVolume  weighted evidence actually collected
"""

import argparse
import json
import math
import os
import shutil
import sqlite3
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import console
from claims import CLAIMS, TOPICS, claims_for_topic, groups_for_topic, tested_text
import design

console.init()

DATA_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "claims.db")
OUT_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "frontend", "public", "claims"))

STRENGTH_WEIGHT = {"strong": 3.0, "moderate": 2.0, "mixed": 1.5, "limited": 1.0}
DEFAULT_WEIGHT = 1.0


# A row judged before 2026-09-02 has `confidence`, which had no definition in
# the prompt and measured only whether the stance was neutral. A row judged
# after has `alignment`, which measures how well the paper answers the claim.
# They are not the same quantity and must not be averaged into one column, so a
# pre-change row gets the neutral value instead of its old number: it neither
# helps nor hurts, and nothing pretends the old figure meant something.
NEUTRAL_ALIGNMENT = 50


def paper_weight(study_type, citations, alignment):
    """Quality x impact x how well the paper answers THIS claim.

    Quality is the study DESIGN, ranked on an evidence hierarchy - not the
    model's own strong/moderate/limited label, which conflated design with
    sample size and ranked position papers above meta-analyses. See design.py.

    The third term was `confidence` until 2026-09-02 and did nothing useful:
    1,013 of the 1,014 verdicts at confidence=30 were neutral, so it restated
    the stance while carrying a 2x multiplier as though it were independent.
    `alignment` at least measures a different thing - though see D26, it is
    still confounded with whether the model took a stance at all.
    """
    base = 1.0 + 2.0 * design.rank_of(study_type)     # 1.0 .. 3.0, as before
    impact = 1.0 + math.log10(1 + max(0, citations or 0))
    a = alignment if alignment is not None else NEUTRAL_ALIGNMENT
    certainty = 0.5 + 0.5 * (a / 100)
    return base * impact * certainty


def open_conn(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def claim_rows(conn, claim_key):
    return conn.execute("""
        SELECT p.paperId, p.title, p.abstract, p.year, p.publicationDate,
               p.cited_by_count, p.all_author_names, p.first_author_name,
               p.all_institution_names, p.venue, p.doi, p.url,
               cp.stance, cp.confidence, cp.alignment, cp.stance_summary,
               cp.evidence_strength, cp.study_type, cp.keyword_score,
               cp.finding, cp.direction,
               s.impact AS journal_impact, s.h_index AS journal_h_index,
               s.display_name AS journal_name
        FROM claim_papers cp
        JOIN papers p USING(paperId)
        LEFT JOIN sources s ON s.source_id = p.source_id
        WHERE cp.claim_key = ?
          -- Retracted work is excluded outright rather than down-weighted. The
          -- one found so far is a Cochrane review cited 1,528 times, which the
          -- design ladder would otherwise have ranked top of its claim.
          AND COALESCE(p.is_retracted, 0) = 0
        ORDER BY p.cited_by_count DESC
    """, (claim_key,)).fetchall()


def evidence_quality_of(ranks):
    """
    How good the evidence on a claim IS, on the 0-1 design ladder.

    Weighted toward the best of it rather than the middle of it, because that is
    how evidence is actually appraised: a question settled by two meta-analyses
    is settled whatever else was published around it, and averaging those two
    against sixty cross-sectional studies reports the state of the literature
    instead of the state of the answer.

    A plain mean put every claim in 0.27-0.80 and averaged 0.40, so the whole
    map sat left of centre and the right-hand half of the axis went unused. The
    maximum overcorrects the other way - 0.50-1.00 averaging 0.95, where one
    meta-analysis owns the claim outright and nothing can be told apart.

    So it is built from the top of the distribution and only checked against the
    whole of it: half the weight on the mean of the best QUARTER, a third on the
    mean of the best TENTH, and the remaining 15% on the overall mean. The best
    tenth is what gives the strongest handful of papers a say of their own; the
    best quarter is what stops any one of them owning the claim - on a claim
    with 180 papers that quartile is 45 of them; and the overall mean is the
    check that keeps fifty strong studies ahead of three strong and two hundred
    weak.

    The weights were chosen against the corpus rather than by taste. A plain
    mean put all eighty claims in 0.27-0.80 averaging 0.40, so the map sat left
    of centre with the right half of the axis unused. A plain maximum ran
    0.50-1.00 averaging 0.95 - one meta-analysis owning the claim, nothing
    distinguishable. Leaning harder still, on the top tenth alone, pushed thirty
    of the eighty into the far-right fifth of the axis, which stops being a
    ranking. This lands at 0.20-0.91 averaging 0.69, spread across the middle
    and right without piling up at either end.
    """
    if not ranks:
        return 0.0
    ordered = sorted(ranks)
    if len(ordered) < 4:
        return sum(ordered) / len(ordered)

    def top_mean(fraction):
        top = ordered[int(len(ordered) * (1 - fraction)):] or ordered
        return sum(top) / len(top)

    overall = sum(ordered) / len(ordered)
    return 0.5 * top_mean(0.25) + 0.35 * top_mean(0.10) + 0.15 * overall


def summarise_claim(conn, claim_key, rows, openalex_count):
    cfg = CLAIMS[claim_key]
    topic = TOPICS[cfg["topic"]]

    counts = {"supports": 0, "refutes": 0, "neutral": 0, "mixed": 0, "unevaluated": 0}
    weights = {"supports": 0.0, "refutes": 0.0, "neutral": 0.0, "mixed": 0.0}
    strength_mix = {"strong": 0, "moderate": 0, "limited": 0, "mixed": 0}

    for r in rows:
        stance = r["stance"]
        # Anything outside the four real verdicts - empty, or a stray literal
        # like "unevaluated" that a restore round-tripped back in - counts as
        # not yet judged. An export must not die on one odd row.
        if stance not in weights:
            counts["unevaluated"] += 1
            continue
        counts[stance] += 1
        weights[stance] += paper_weight(r["study_type"], r["cited_by_count"],
                                        r["alignment"])
        if r["evidence_strength"] in strength_mix:
            strength_mix[r["evidence_strength"]] += 1

    # A paper that cuts both ways has no single honest position on a
    # supported/refuted axis, so the reader gets to choose how to read it. All
    # three readings ship, and the UI switches between them:
    #
    #   conservative  the claim is technically supported, caveats notwithstanding
    #                 -> mixed weight counts toward SUPPORTS
    #   balanced      a two-sided paper takes no side
    #                 -> mixed weight is set aside entirely
    #   liberal       the caveats matter as much as the headline
    #                 -> mixed weight counts toward REFUTES
    #
    # The spread between the three IS the signal: a claim that reads +0.6 or
    # -0.1 depending on how you treat its mixed papers is not a settled claim.
    def _net(sup, ref):
        total = sup + ref
        return (sup - ref) / total if total else 0.0

    net_balanced = _net(weights["supports"], weights["refutes"])
    net_conservative = _net(weights["supports"] + weights["mixed"], weights["refutes"])
    net_liberal = _net(weights["supports"], weights["refutes"] + weights["mixed"])

    net_support = net_balanced
    evidence_volume = (weights["supports"] + weights["refutes"] + weights["mixed"]
                       + 0.25 * weights["neutral"])

    # Mean study-design quality across every assessed paper, normalised to 0..1
    # (1.0 = all meta-analyses / large RCTs, 0.0 = all small cross-sectional).
    # This is the Y axis of the claims view: it separates "well supported by
    # strong studies" from "well supported by weak ones", which net_support
    # alone cannot distinguish.
    assessed = [r for r in rows if r["stance"]]
    if assessed:
        # Mean design rank, which is already 0..1 - so a claim's X is exactly the
        # mean of its papers' X, the same identity the evidence view relies on.
        evidence_quality = evidence_quality_of(
            [design.rank_of(r["study_type"]) for r in assessed])
    else:
        evidence_quality = 0.0

    return {
        "id": claim_key,
        "claim": cfg["claim"],
        # What a study can actually measure. Differs from the headline only for
        # prescriptive claims; shown in the UI so the reader can see what was
        # tested on their behalf without having to phrase it themselves.
        "testedAs": tested_text(claim_key),
        "isPrescriptive": bool(cfg.get("tested_as")),
        "topic": cfg["topic"],
        "topicName": topic["name"],
        "group": cfg["group"],
        "ageRange": cfg.get("age_range", ""),
        "query": cfg["query"],
        # what we hold
        "paperCount": len(rows),
        "supports": counts["supports"],
        "refutes": counts["refutes"],
        "neutral": counts["neutral"],
        "mixed": counts["mixed"],
        "unevaluated": counts["unevaluated"],
        "strengthMix": strength_mix,
        "hasEvidence": len(rows) > 0,
        # geometry
        "openAlexCount": openalex_count,                    # node SIZE
        "netSupport": round(net_support, 3),                # Y axis (balanced)
        "netSupportConservative": round(net_conservative, 3),
        "netSupportBalanced": round(net_balanced, 3),
        "netSupportLiberal": round(net_liberal, 3),
        "evidenceQuality": round(max(0.0, min(1.0, evidence_quality)), 3),  # Y axis
        "evidenceVolume": round(evidence_volume, 2),
        "consensus": round(abs(net_support), 3),
    }


# The journal metric tops out around 120 and is worthless linearly - the gap
# between 1 and 3 matters far more than the one between 40 and 50 - so it is
# compressed on a log scale against a ceiling of 20, which is already an
# exceptional journal.
JOURNAL_CEILING = 20.0

# The three weights, named because the card now shows them to a reader. They
# have never been calibrated against anything - see DECISIONS D23 - so they are
# a starting point held in one place, not a result.
W_DESIGN = 0.45
W_CITATIONS = 0.35
W_JOURNAL = 0.20


def importance_of(row, max_log_cites):
    """
    How much a paper should count as evidence: (total 0..1, contributions).

    The contributions are returned rather than recovered later because the card
    shows them, and a second implementation of the same arithmetic is a second
    thing that can disagree with the ranking.

    Three things, because any one alone is misleading. Design alone would rank a
    tiny flawless RCT above a definitive meta-analysis. Citations alone reward
    age and fashion, and a 1998 paper will always beat a 2024 one. The journal
    alone says nothing about the specific paper. Together they answer "which of
    these should I read first", which is the question a reader actually has.

    Citations are normalised WITHIN the claim, so rank 1 means the most
    important paper on this question rather than the most cited paper in
    paediatrics. The journal metric is absolute - a strong journal is a strong
    journal whichever claim it turns up under.
    """
    design_rank = design.rank_of(row["study_type"])

    cites = row["cited_by_count"] or 0
    cites_norm = (math.log1p(cites) / max_log_cites) if max_log_cites > 0 else 0.0

    impact = row["journal_impact"] if "journal_impact" in row.keys() else None
    journal_norm = (math.log1p(min(impact or 0.0, JOURNAL_CEILING))
                    / math.log1p(JOURNAL_CEILING))

    design_part = W_DESIGN * design_rank
    cites_part = W_CITATIONS * cites_norm
    journal_part = W_JOURNAL * journal_norm

    # Total from the unrounded parts. Summing the rounded ones instead would
    # move it by up to 1.5e-4, which is enough to swap two papers whose scores
    # are otherwise identical - a rendering detail silently reordering a rank.
    total = max(0.0, min(1.0, design_part + cites_part + journal_part))
    return total, {
        "design": round(design_part, 4),
        "citations": round(cites_part, 4),
        "journal": round(journal_part, 4),
    }


def rank_papers(papers):
    """
    Rank in place, 1 = read this first. Ties break on citations, then id, so
    the order is total and stable across rebuilds.

    The rank covers every paper held for the claim, including the weakly-cited
    neutrals the evidence view filters out of the picture. That means a visible
    paper can be #151 of 151 with only 116 on screen, which is why the total
    travels with it - "#151" alone would look like a bug.
    """
    order = sorted(papers,
                   key=lambda p: (-p["importance"], -(p["citationCount"] or 0), p["id"]))
    for i, p in enumerate(order, 1):
        p["rank"] = i
        p["rankTotal"] = len(order)
    return papers


def build_paper_node(row):
    return {
        "id": row["paperId"],
        "title": row["title"],
        "abstract": row["abstract"] or "",
        "year": row["year"],
        "publicationDate": row["publicationDate"],
        "citationCount": row["cited_by_count"] or 0,
        "authors": row["all_author_names"] or "",
        "firstAuthor": row["first_author_name"] or "",
        "institutions": row["all_institution_names"] or "",
        "venue": row["venue"] or "",
        "doi": row["doi"] or "",
        "url": row["url"] or "",
        "stance": row["stance"] or "unevaluated",
        "confidence": row["confidence"],
        "stanceSummary": row["stance_summary"] or "",
        "evidenceStrength": row["evidence_strength"] or "",
        "studyType": row["study_type"] or "",
        # Canonical design and its place on the evidence hierarchy. designRank
        # drives the horizontal axis; the raw studyType is kept so a reader can
        # see what the model actually called it.
        "studyDesign": design.design_of(row["study_type"]),
        "designRank": round(design.rank_of(row["study_type"]), 3),
        # The model's own restatement of the result, and the agree/disagree call
        # it made before picking a stance. Surfaced so a reader can see WHY a
        # badge says what it says, and catch it when the two disagree.
        "finding": (row["finding"] if "finding" in row.keys() else "") or "",
        "direction": (row["direction"] if "direction" in row.keys() else "") or "",
        # BACKLOG item 2: this passed `evidence_strength` where `study_type`
        # belongs, so design.rank_of() was handed "strong"/"moderate"/"limited",
        # matched none of them, and returned the UNKNOWN rank of 0.30 for every
        # card. The number shown on a paper card was therefore the same design
        # score whatever the design, while the claim-level aggregate above used
        # the right one - so the card and the map disagreed by construction.
        "weight": round(paper_weight(row["study_type"], row["cited_by_count"],
                                     row["alignment"]), 2),
        # Where it was published, and how that journal performs. OpenAlex's
        # 2yr_mean_citedness is the same quantity a journal impact factor
        # measures - mean citations over the prior two years - and unlike the
        # real thing it is free and covers everything indexed.
        "journalName": (row["journal_name"] if "journal_name" in row.keys() else None) or "",
        "journalImpact": (round(row["journal_impact"], 2)
                          if "journal_impact" in row.keys() and row["journal_impact"] is not None
                          else None),
        "journalHIndex": (row["journal_h_index"] if "journal_h_index" in row.keys() else None),
    }


def export_evidence(conn, claim_key, summary, rows, out_dir):
    papers = [build_paper_node(r) for r in rows]

    # Importance and rank are per claim, so they are computed here where the
    # whole set is in hand rather than per row.
    max_log_cites = max((math.log1p(r["cited_by_count"] or 0) for r in rows), default=0.0)
    for node, row in zip(papers, rows):
        total, parts = importance_of(row, max_log_cites)
        node["importance"] = round(total, 4)
        # The three contributions travel with the paper so the open card can
        # show WHY it ranks where it does. Recomputing them in the frontend
        # would need max_log_cites over every paper held for the claim, and the
        # frontend has already dropped most of the neutrals by then - so it
        # would quietly disagree with the ranking it is explaining.
        node["importanceParts"] = parts
    rank_papers(papers)

    edges = []
    if papers:
        ids = [p["id"] for p in papers]
        ph = ",".join("?" * len(ids))
        edges = [
            {"source": r["source"], "target": r["target"]}
            for r in conn.execute(
                f"SELECT source, target FROM citations "
                f"WHERE source IN ({ph}) AND target IN ({ph})", ids + ids
            ).fetchall()
        ]

    topic_key = CLAIMS[claim_key]["topic"]
    claim_dir = os.path.join(out_dir, topic_key, claim_key)
    os.makedirs(claim_dir, exist_ok=True)
    with open(os.path.join(claim_dir, "evidence.json"), "w", encoding="utf-8") as f:
        json.dump({"claim": summary, "papers": papers, "edges": edges}, f,
                  separators=(",", ":"))
    return len(edges)


def build(db_path=DB_PATH, out_dir=OUT_DIR, clean=False):
    if not os.path.exists(db_path):
        raise SystemExit(f"[error] {db_path} not found - run import_claims.py first")

    if clean and os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    conn = open_conn(db_path)
    try:
        counts = {
            r["claim_key"]: r["openalex_count"]
            for r in conn.execute(
                "SELECT claim_key, openalex_count FROM claim_meta").fetchall()
        }

        topics_out = []
        for topic_key, topic_cfg in TOPICS.items():
            topic_claims = claims_for_topic(topic_key)
            summaries = []

            for claim_key in topic_claims:
                rows = claim_rows(conn, claim_key)
                summary = summarise_claim(conn, claim_key, rows,
                                          counts.get(claim_key, 0))
                # Every claim is exported, researched or not - an empty claim is
                # still a node on the map, sized by its literature.
                n_edges = export_evidence(conn, claim_key, summary, rows, out_dir)
                summaries.append(summary)
                flag = "" if summary["hasEvidence"] else "  (no evidence yet)"
                print(f"  [{topic_key:8s}] {claim_key:30s} "
                      f"{summary['openAlexCount']:>8,d} matching  "
                      f"{summary['paperCount']:>4d} held  "
                      f"S{summary['supports']:<3d} R{summary['refutes']:<3d} "
                      f"M{summary['mixed']:<3d} N{summary['neutral']:<3d}  "
                      f"net {summary['netSupport']:+.2f}"
                      f"{flag}")

            summaries.sort(key=lambda s: -s["openAlexCount"])
            topic_dir = os.path.join(out_dir, topic_key)
            os.makedirs(topic_dir, exist_ok=True)
            with open(os.path.join(topic_dir, "claims.json"), "w", encoding="utf-8") as f:
                json.dump({
                    "id": topic_key,
                    "name": topic_cfg["name"],
                    "colour": topic_cfg["colour"],
                    "blurb": topic_cfg["blurb"],
                    "groups": groups_for_topic(topic_key),
                    "claims": summaries,
                }, f, separators=(",", ":"))

            supports = sum(s["supports"] for s in summaries)
            refutes = sum(s["refutes"] for s in summaries)
            decisive = supports + refutes
            researched = sum(1 for s in summaries if s["hasEvidence"])

            topics_out.append({
                "id": topic_key,
                "name": topic_cfg["name"],
                "colour": topic_cfg["colour"],
                "blurb": topic_cfg["blurb"],
                "claimCount": len(summaries),
                "researchedClaimCount": researched,
                # Sum of the topic's claim queries. Those queries overlap, so this
                # is an upper bound on distinct literature, not a precise count -
                # the UI says "~N" for that reason. It drives node SIZE.
                "openAlexCount": sum(s["openAlexCount"] for s in summaries),
                "paperCount": sum(s["paperCount"] for s in summaries),
                "supports": supports,
                "refutes": refutes,
                "neutral": sum(s["neutral"] for s in summaries),
                "mixed": sum(s["mixed"] for s in summaries),
                "netSupport": round((supports - refutes) / decisive, 3) if decisive else 0.0,
                "evidenceVolume": round(sum(s["evidenceVolume"] for s in summaries), 2),
                "iconPath": f"images/topics/{topic_key}.jpg",
            })

        topics_out.sort(key=lambda t: -t["openAlexCount"])

        payload = {
            "version": 3,
            "description": "Map of Baby Science by Topic",
            "topics": topics_out,
            "stats": {
                "topics": len(topics_out),
                "claims": len(CLAIMS),
                "researchedClaims": sum(t["researchedClaimCount"] for t in topics_out),
                "papers": conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0],
                "evaluated": conn.execute(
                    "SELECT COUNT(*) FROM claim_papers WHERE stance IS NOT NULL"
                ).fetchone()[0],
            },
        }
        with open(os.path.join(out_dir, "topics.json"), "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

        print(f"\n[build] {payload['stats']['claims']} claims across "
              f"{len(topics_out)} topics -> {out_dir}")
        print(f"[build] {payload['stats']['researchedClaims']} claims have evidence; "
              f"{payload['stats']['papers']} papers, "
              f"{payload['stats']['evaluated']} evaluated")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Export claims.db to frontend JSON")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--out-dir", default=OUT_DIR)
    parser.add_argument("--clean", action="store_true",
                        help="delete the output directory first")
    args = parser.parse_args()
    build(args.db, args.out_dir, clean=args.clean)


if __name__ == "__main__":
    main()
