#!/usr/bin/env python3
"""
build_data.py — Generates universe.json and per-galaxy JSON files from SQLite databases.

Reads all papers_*.db files from the data directory and produces:
  - frontend/public/universe.json  — galaxy-level summary nodes
  - frontend/public/data/<topic>/nodes.json
  - frontend/public/data/<topic>/edges.json

Usage:
    python build_data.py
    python build_data.py --data-dir ../data --out-dir ../frontend/public
"""

import argparse
import glob
import json
import os
import sqlite3

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..', 'data'))
OUT_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..', 'frontend', 'public'))

# Maps topic key → icon category (for loremflickr via categoryIcons.js)
TOPIC_ICON_MAP = {
    "peanut_allergy":          "peanuts",
    "tree_nut_allergy":        "tree-nuts",
    "egg_allergy":             "eggs",
    "cow_milk_allergy":        "cow-milk",
    "complementary_feeding":   "solid-food",
    "breastfeeding":           "breast-milk",
    "infant_formula":          "formula",
    "iron_deficiency":         "iron",
    "vitamin_d":               "vitamin-d",
    "gut_microbiome":          "probiotics",
    "baby_led_weaning":        "solid-food",
    "sugar_salt_babies":       "general",
    "omega3_dha":              "omega3",
    "vegetable_introduction":  "vegetables",
    "food_texture_progression":"solid-food",
}

# Maps primary_field → galaxy group
FIELD_TO_GROUP = {
    "Allergen Introduction":   "allergens",
    "Feeding Milestones":      "feeding",
    "Nutrients & Supplements": "nutrition",
    "Food Safety":             "safety",
    "Gut Health":              "gut",
    "Growth & Development":    "development",
    "Breastfeeding & Formula": "feeding",
}


def topic_key_from_path(db_path):
    return os.path.basename(db_path).replace("papers_", "").replace(".db", "")


def topic_name(key):
    return key.replace("_", " ").title()


def open_conn(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def build_galaxy_node(topic_key, conn, data_sub_path):
    rows = conn.execute(
        "SELECT year, cited_by_count, AI_primary_field FROM papers"
    ).fetchall()
    if not rows:
        return None

    total = len(rows)
    total_citations = sum(r["cited_by_count"] or 0 for r in rows)
    years = [r["year"] for r in rows if r["year"]]

    works_by_decade = {}
    for r in rows:
        if r["year"]:
            decade = f"{(r['year'] // 10) * 10}s"
            works_by_decade[decade] = works_by_decade.get(decade, 0) + 1

    # Dominant primary field
    field_counts = {}
    for r in rows:
        f = r["AI_primary_field"] or "Unassigned"
        field_counts[f] = field_counts.get(f, 0) + 1
    dominant_field = max(field_counts, key=field_counts.get) if field_counts else "Unassigned"
    group = FIELD_TO_GROUP.get(dominant_field, "general")

    icon_category = TOPIC_ICON_MAP.get(topic_key, "general")

    return {
        "id": topic_key,
        "name": topic_name(topic_key),
        "group": group,
        "primaryField": dominant_field,
        "totalWorksCount": total,
        "totalCitations": total_citations,
        "iconCategory": icon_category,
        "hasPapers": True,
        "nodesFile": f"data/{topic_key}/nodes.json",
        "edgesFile": f"data/{topic_key}/edges.json",
        "worksByDecade": works_by_decade,
        "yearRange": [min(years), max(years)] if years else [2000, 2024],
    }


def build_paper_node(row):
    yr = row["year"]
    pub_date = row["publicationDate"] or ""
    if not yr and pub_date:
        try:
            yr = int(pub_date.split("-")[0])
        except Exception:
            yr = 2000

    cite_count = row["cited_by_count"] or 0

    return {
        "id": row["paperId"],
        "title": row["title"] or "",
        "year": yr,
        "citationCount": cite_count,
        "primaryField": row["AI_primary_field"] or "Unassigned",
        "abstract": row["AI_summary"] or row["abstract"] or "",
        "authors": row["all_author_names"] or row["first_author_name"] or "Unknown",
        "institutions": row["all_institution_names"] or "",
        "paperNature": row["paper_nature"],
        "foodType": row["food_type"],
        "ageGroup": row["age_group"],
        "recommendationSummary": row["recommendation_summary"],
        "evidenceStrength": row["evidence_strength"],
        "likelihoodScore": row["likelihood_score"],
        "seriousnessScore": row["seriousness_score"],
        "participantCount": row["participant_count"],
        "studyType": row["study_type"] or row["paper_nature"],
        "iconCategory": row["food_type"],
        "doi": row["doi"] or "",
        "url": row["url"] or "",
    }


def export_topic(topic_key, db_path, out_dir):
    conn = open_conn(db_path)
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "papers" not in tables:
            print(f"  [skip] {topic_key}: no papers table")
            return None

        rows = conn.execute("SELECT * FROM papers").fetchall()
        if not rows:
            print(f"  [skip] {topic_key}: empty")
            return None

        nodes = [build_paper_node(r) for r in rows]

        edge_rows = []
        if "citations" in tables:
            edge_rows = conn.execute("SELECT source, target FROM citations").fetchall()
        valid_ids = {n["id"] for n in nodes}
        edges = [
            {"source": r["source"], "target": r["target"], "importance": 1}
            for r in edge_rows
            if r["source"] in valid_ids and r["target"] in valid_ids
        ]

        topic_out = os.path.join(out_dir, "data", topic_key)
        os.makedirs(topic_out, exist_ok=True)
        with open(os.path.join(topic_out, "nodes.json"), "w") as f:
            json.dump(nodes, f, separators=(",", ":"))
        with open(os.path.join(topic_out, "edges.json"), "w") as f:
            json.dump(edges, f, separators=(",", ":"))

        galaxy_node = build_galaxy_node(topic_key, conn, f"data/{topic_key}")
        print(f"  [ok] {topic_key}: {len(nodes)} papers, {len(edges)} citations")
        return galaxy_node

    finally:
        conn.close()


def build_universe(data_dir, out_dir):
    dbs = sorted(glob.glob(os.path.join(data_dir, "papers_*.db")))
    if not dbs:
        print(f"[warn] No databases found in {data_dir}")
        print("Run import_openalex.py first.")
        return

    print(f"[build] Found {len(dbs)} databases")
    galaxy_nodes = []
    for db_path in dbs:
        key = topic_key_from_path(db_path)
        print(f"[build] Processing {key}...")
        node = export_topic(key, db_path, out_dir)
        if node:
            galaxy_nodes.append(node)

    universe = {
        "version": 1,
        "description": "Map of Baby Food Science — evidence-based nutrition research",
        "galaxies": galaxy_nodes,
    }

    universe_path = os.path.join(out_dir, "universe.json")
    with open(universe_path, "w") as f:
        json.dump(universe, f, indent=2)
    print(f"\n[build] universe.json written: {universe_path}")
    print(f"[build] {len(galaxy_nodes)} galaxy nodes")


def main():
    parser = argparse.ArgumentParser(description="Build universe.json and topic JSON from SQLite DBs")
    parser.add_argument("--data-dir", default=DATA_DIR, help="SQLite DB directory")
    parser.add_argument("--out-dir", default=OUT_DIR, help="Output directory (frontend/public)")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    build_universe(args.data_dir, args.out_dir)


if __name__ == "__main__":
    main()
