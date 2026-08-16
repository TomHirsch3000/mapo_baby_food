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

    netSupport   -1 (refuted) .. +1 (supported); drives X POSITION
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
from claims import CLAIMS, TOPICS, claims_for_topic, groups_for_topic

console.init()

DATA_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "claims.db")
OUT_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "frontend", "public", "claims"))

STRENGTH_WEIGHT = {"strong": 3.0, "moderate": 2.0, "mixed": 1.5, "limited": 1.0}
DEFAULT_WEIGHT = 1.0


def paper_weight(evidence_strength, citations, confidence):
    """Quality x impact x how sure the evaluator was."""
    base = STRENGTH_WEIGHT.get(evidence_strength, DEFAULT_WEIGHT)
    impact = 1.0 + math.log10(1 + max(0, citations or 0))
    certainty = 0.5 + 0.5 * ((confidence if confidence is not None else 50) / 100)
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
               cp.stance, cp.confidence, cp.stance_summary,
               cp.evidence_strength, cp.study_type, cp.keyword_score
        FROM claim_papers cp
        JOIN papers p USING(paperId)
        WHERE cp.claim_key = ?
        ORDER BY p.cited_by_count DESC
    """, (claim_key,)).fetchall()


def summarise_claim(conn, claim_key, rows, openalex_count):
    cfg = CLAIMS[claim_key]
    topic = TOPICS[cfg["topic"]]

    counts = {"supports": 0, "refutes": 0, "neutral": 0, "unevaluated": 0}
    weights = {"supports": 0.0, "refutes": 0.0, "neutral": 0.0}
    strength_mix = {"strong": 0, "moderate": 0, "limited": 0, "mixed": 0}

    for r in rows:
        stance = r["stance"]
        if not stance:
            counts["unevaluated"] += 1
            continue
        counts[stance] += 1
        weights[stance] += paper_weight(r["evidence_strength"], r["cited_by_count"],
                                        r["confidence"])
        if r["evidence_strength"] in strength_mix:
            strength_mix[r["evidence_strength"]] += 1

    decisive = weights["supports"] + weights["refutes"]
    net_support = (weights["supports"] - weights["refutes"]) / decisive if decisive else 0.0
    evidence_volume = weights["supports"] + weights["refutes"] + 0.25 * weights["neutral"]

    # Mean study-design quality across every assessed paper, normalised to 0..1
    # (1.0 = all meta-analyses / large RCTs, 0.0 = all small cross-sectional).
    # This is the Y axis of the claims view: it separates "well supported by
    # strong studies" from "well supported by weak ones", which net_support
    # alone cannot distinguish.
    assessed = [r for r in rows if r["stance"]]
    if assessed:
        quality_sum = sum(STRENGTH_WEIGHT.get(r["evidence_strength"], DEFAULT_WEIGHT)
                          for r in assessed)
        evidence_quality = (quality_sum / len(assessed) - DEFAULT_WEIGHT) / (3.0 - DEFAULT_WEIGHT)
    else:
        evidence_quality = 0.0

    return {
        "id": claim_key,
        "claim": cfg["claim"],
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
        "unevaluated": counts["unevaluated"],
        "strengthMix": strength_mix,
        "hasEvidence": len(rows) > 0,
        # geometry
        "openAlexCount": openalex_count,                    # node SIZE
        "netSupport": round(net_support, 3),                # X axis
        "evidenceQuality": round(max(0.0, min(1.0, evidence_quality)), 3),  # Y axis
        "evidenceVolume": round(evidence_volume, 2),
        "consensus": round(abs(net_support), 3),
    }


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
        "weight": round(paper_weight(row["evidence_strength"], row["cited_by_count"],
                                     row["confidence"]), 2),
    }


def export_evidence(conn, claim_key, summary, rows, out_dir):
    papers = [build_paper_node(r) for r in rows]

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
                      f"N{summary['neutral']:<3d}  net {summary['netSupport']:+.2f}"
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
