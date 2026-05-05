#!/usr/bin/env python3
"""
import_openalex.py — Fetches papers from the OpenAlex API for baby food topics
and stores them in per-topic SQLite databases.

Usage:
    python import_openalex.py --topic peanut_allergy --max 500
    python import_openalex.py --topic infant_nutrition --query "infant complementary feeding" --max 300
    python import_openalex.py --list-topics
"""

import argparse
import os
import sqlite3
import time
import json
import re
import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..', 'data'))

OPENALEX_BASE = "https://api.openalex.org"
EMAIL = os.environ.get("OPENALEX_EMAIL", "research@example.com")

# Pre-defined baby food topics with curated search queries
PREDEFINED_TOPICS = {
    "peanut_allergy": {
        "name": "Peanut Allergy",
        "query": "peanut allergy infant introduction early",
        "concepts": ["C2776082936"],  # Allergy
        "food_type_hint": "peanuts",
        "age_hint": "infant",
    },
    "tree_nut_allergy": {
        "name": "Tree Nut Allergy",
        "query": "tree nut allergy children introduction",
        "food_type_hint": "tree-nuts",
        "age_hint": "infant",
    },
    "egg_allergy": {
        "name": "Egg Allergy",
        "query": "egg allergy infant introduction prevention",
        "food_type_hint": "eggs",
        "age_hint": "infant",
    },
    "cow_milk_allergy": {
        "name": "Cow Milk Allergy",
        "query": "cow milk protein allergy infant formula",
        "food_type_hint": "cow-milk",
        "age_hint": "infant",
    },
    "complementary_feeding": {
        "name": "Complementary Feeding",
        "query": "complementary feeding infant solid foods introduction weaning",
        "food_type_hint": "solid-food",
        "age_hint": "6-12 months",
    },
    "breastfeeding": {
        "name": "Breastfeeding",
        "query": "breastfeeding infant nutrition benefits outcomes",
        "food_type_hint": "breast-milk",
        "age_hint": "0-6 months",
    },
    "infant_formula": {
        "name": "Infant Formula",
        "query": "infant formula nutrition comparison breastfeeding",
        "food_type_hint": "formula",
        "age_hint": "0-12 months",
    },
    "iron_deficiency": {
        "name": "Iron Deficiency",
        "query": "iron deficiency anemia infant toddler supplementation",
        "food_type_hint": "iron",
        "age_hint": "6-24 months",
    },
    "vitamin_d": {
        "name": "Vitamin D",
        "query": "vitamin D deficiency infant supplementation rickets",
        "food_type_hint": "vitamin-d",
        "age_hint": "0-12 months",
    },
    "gut_microbiome": {
        "name": "Gut Microbiome",
        "query": "infant gut microbiome probiotics diet early life",
        "food_type_hint": "probiotics",
        "age_hint": "0-24 months",
    },
    "baby_led_weaning": {
        "name": "Baby-Led Weaning",
        "query": "baby-led weaning self-feeding solid foods infant",
        "food_type_hint": "solid-food",
        "age_hint": "6-12 months",
    },
    "sugar_salt_babies": {
        "name": "Sugar and Salt",
        "query": "sugar salt intake infant toddler processed food",
        "food_type_hint": "general",
        "age_hint": "6-36 months",
    },
    "omega3_dha": {
        "name": "Omega-3 / DHA",
        "query": "omega-3 DHA infant brain development fish oil",
        "food_type_hint": "omega3",
        "age_hint": "0-12 months",
    },
    "vegetable_introduction": {
        "name": "Vegetable Introduction",
        "query": "vegetable acceptance infant repeated exposure food neophobia",
        "food_type_hint": "vegetables",
        "age_hint": "4-12 months",
    },
    "food_texture_progression": {
        "name": "Food Texture Progression",
        "query": "food texture lumpy pureed infant feeding development",
        "food_type_hint": "solid-food",
        "age_hint": "6-18 months",
    },
}


def create_db(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS papers (
            paperId TEXT PRIMARY KEY,
            title TEXT,
            abstract TEXT,
            year INTEGER,
            publicationDate TEXT,
            cited_by_count INTEGER,
            all_author_names TEXT,
            first_author_name TEXT,
            all_institution_names TEXT,
            AI_primary_field TEXT,
            AI_summary TEXT,
            paper_nature TEXT,
            food_type TEXT,
            age_group TEXT,
            recommendation_summary TEXT,
            evidence_strength TEXT,
            likelihood_score REAL,
            seriousness_score REAL,
            participant_count INTEGER,
            study_type TEXT,
            doi TEXT,
            url TEXT,
            raw_json TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS citations (
            source TEXT,
            target TEXT,
            PRIMARY KEY (source, target)
        )
    """)
    conn.commit()
    return conn


def reconstruct_abstract(inverted_index):
    if not inverted_index:
        return ""
    positions = {}
    for word, pos_list in inverted_index.items():
        for pos in pos_list:
            positions[pos] = word
    return " ".join(positions[k] for k in sorted(positions.keys()))


def fetch_works(query, concepts=None, max_results=200, filter_str=None):
    """Cursor-based pagination from OpenAlex /works."""
    headers = {"User-Agent": f"mapo-baby-food/1.0 (mailto:{EMAIL})"}
    filters = [
        "type:article",
        "has_abstract:true",
    ]
    if filter_str:
        filters.append(filter_str)
    if concepts:
        filters.append(f"concepts.id:{'|'.join(concepts)}")

    params = {
        "search": query,
        "filter": ",".join(filters),
        "per-page": 200,
        "cursor": "*",
        "select": (
            "id,title,abstract_inverted_index,publication_year,publication_date,"
            "cited_by_count,authorships,primary_location,referenced_works,"
            "topics,concepts,type"
        ),
    }

    fetched = []
    while len(fetched) < max_results:
        resp = requests.get(f"{OPENALEX_BASE}/works", params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        if not results:
            break
        fetched.extend(results)
        print(f"  Fetched {len(fetched)} papers...", end="\r")
        cursor = data.get("meta", {}).get("next_cursor")
        if not cursor:
            break
        params["cursor"] = cursor
        time.sleep(0.1)

    print(f"  Fetched {len(fetched)} papers total.   ")
    return fetched[:max_results]


def parse_paper(work, food_type_hint="general", age_hint=None):
    paper_id = work["id"].replace("https://openalex.org/", "")
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))

    authors = work.get("authorships", [])
    author_names = [
        a["author"]["display_name"] for a in authors
        if a.get("author") and a["author"].get("display_name")
    ]
    institutions = []
    for a in authors:
        for inst in a.get("institutions", []):
            if inst.get("display_name"):
                institutions.append(inst["display_name"])

    first_author = author_names[0] if author_names else "Unknown"

    # Determine study type from type field and topics
    work_type = work.get("type", "")
    topics = work.get("topics", []) or []
    topic_names = [t.get("display_name", "") for t in topics]

    study_type = "review" if "review" in work_type.lower() else "article"
    paper_nature = "review"
    if any(k in " ".join(topic_names).lower() for k in ["trial", "rct", "randomized"]):
        paper_nature = "clinical_trial"
        study_type = "clinical_trial"
    elif any(k in " ".join(topic_names).lower() for k in ["cohort", "longitudinal", "prospective"]):
        paper_nature = "experimental"
        study_type = "cohort"
    elif "meta-analysis" in " ".join(topic_names).lower():
        paper_nature = "meta_analysis"
        study_type = "meta_analysis"
    elif abstract and any(k in abstract.lower() for k in ["randomized", "randomised", "placebo"]):
        paper_nature = "clinical_trial"
        study_type = "clinical_trial"

    doi = ""
    url = ""
    primary_loc = work.get("primary_location") or {}
    source = primary_loc.get("source") or {}
    if primary_loc.get("doi"):
        doi = primary_loc["doi"]
        url = f"https://doi.org/{doi.replace('https://doi.org/', '')}"

    return {
        "paperId": paper_id,
        "title": work.get("title", ""),
        "abstract": abstract,
        "year": work.get("publication_year"),
        "publicationDate": work.get("publication_date", ""),
        "cited_by_count": work.get("cited_by_count", 0),
        "all_author_names": "; ".join(author_names),
        "first_author_name": first_author,
        "all_institution_names": "; ".join(dict.fromkeys(institutions)),
        "food_type": food_type_hint,
        "age_group": age_hint or "",
        "doi": doi,
        "url": url,
        "paper_nature": paper_nature,
        "study_type": study_type,
        "raw_json": json.dumps(work),
        # Fields to be filled by process_ai.py
        "AI_primary_field": None,
        "AI_summary": None,
        "recommendation_summary": None,
        "evidence_strength": None,
        "likelihood_score": None,
        "seriousness_score": None,
        "participant_count": None,
    }, [r.replace("https://openalex.org/", "") for r in work.get("referenced_works", [])]


def import_topic(topic_key, query=None, max_results=200, min_citations=0):
    if topic_key in PREDEFINED_TOPICS:
        cfg = PREDEFINED_TOPICS[topic_key]
        query = query or cfg["query"]
        food_type_hint = cfg.get("food_type_hint", "general")
        age_hint = cfg.get("age_hint")
        concepts = cfg.get("concepts")
    else:
        food_type_hint = "general"
        age_hint = None
        concepts = None
        if not query:
            query = topic_key.replace("_", " ")

    os.makedirs(DATA_DIR, exist_ok=True)
    db_path = os.path.join(DATA_DIR, f"papers_{topic_key}.db")
    print(f"[import] Topic: {topic_key}")
    print(f"[import] Query: {query}")
    print(f"[import] DB: {db_path}")

    conn = create_db(db_path)
    existing = {r[0] for r in conn.execute("SELECT paperId FROM papers").fetchall()}
    print(f"[import] Existing papers: {len(existing)}")

    works = fetch_works(query, concepts=concepts, max_results=max_results)

    inserted, skipped, citation_pairs = 0, 0, []
    for work in works:
        paper, ref_ids = parse_paper(work, food_type_hint, age_hint)
        if work.get("cited_by_count", 0) < min_citations:
            skipped += 1
            continue
        if paper["paperId"] in existing:
            skipped += 1
            continue
        conn.execute("""
            INSERT OR IGNORE INTO papers
            (paperId, title, abstract, year, publicationDate, cited_by_count,
             all_author_names, first_author_name, all_institution_names,
             food_type, age_group, doi, url, paper_nature, study_type,
             AI_primary_field, AI_summary, recommendation_summary,
             evidence_strength, likelihood_score, seriousness_score,
             participant_count, raw_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            paper["paperId"], paper["title"], paper["abstract"], paper["year"],
            paper["publicationDate"], paper["cited_by_count"],
            paper["all_author_names"], paper["first_author_name"],
            paper["all_institution_names"], paper["food_type"], paper["age_group"],
            paper["doi"], paper["url"], paper["paper_nature"], paper["study_type"],
            paper["AI_primary_field"], paper["AI_summary"],
            paper["recommendation_summary"], paper["evidence_strength"],
            paper["likelihood_score"], paper["seriousness_score"],
            paper["participant_count"], paper["raw_json"]
        ))
        citation_pairs.extend(
            (paper["paperId"], ref_id) for ref_id in ref_ids
        )
        inserted += 1

    # Insert citations between papers in this DB
    existing_ids = {r[0] for r in conn.execute("SELECT paperId FROM papers").fetchall()}
    citation_count = 0
    for source, target in citation_pairs:
        if source in existing_ids and target in existing_ids:
            conn.execute("INSERT OR IGNORE INTO citations (source, target) VALUES (?,?)", (source, target))
            citation_count += 1

    conn.commit()
    conn.close()
    print(f"[import] Done. Inserted: {inserted}, Skipped: {skipped}, Citations: {citation_count}")
    return db_path


def main():
    parser = argparse.ArgumentParser(description="Import baby food papers from OpenAlex")
    parser.add_argument("--topic", help="Topic key (use --list-topics to see options)")
    parser.add_argument("--query", help="Custom search query (overrides default for topic)")
    parser.add_argument("--max", type=int, default=200, help="Max papers to fetch (default: 200)")
    parser.add_argument("--min-citations", type=int, default=0, help="Min citations filter")
    parser.add_argument("--list-topics", action="store_true", help="List predefined topics")
    parser.add_argument("--all", action="store_true", help="Import all predefined topics")
    args = parser.parse_args()

    if args.list_topics:
        print("\nPredefined topics:")
        for key, cfg in PREDEFINED_TOPICS.items():
            print(f"  {key:30s} — {cfg['name']}")
        return

    if args.all:
        for key in PREDEFINED_TOPICS:
            print(f"\n{'='*60}")
            import_topic(key, max_results=args.max, min_citations=args.min_citations)
        return

    if not args.topic:
        parser.print_help()
        return

    import_topic(args.topic, query=args.query, max_results=args.max, min_citations=args.min_citations)


if __name__ == "__main__":
    main()
