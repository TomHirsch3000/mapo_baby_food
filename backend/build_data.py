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
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..', 'data'))
OUT_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..', 'frontend', 'public'))

sys.path.insert(0, SCRIPT_DIR)
from import_openalex import PREDEFINED_TOPICS

# Derive icon map and group map from PREDEFINED_TOPICS so they stay in sync
TOPIC_ICON_MAP = {k: v.get("food_type_hint", "general") for k, v in PREDEFINED_TOPICS.items()}

TOPIC_GROUP_MAP = {
    # allergens
    "peanut_allergy": "allergens", "egg_allergy": "allergens", "cow_milk_allergy": "allergens",
    "tree_nut_allergy": "allergens", "wheat_gluten_allergy": "allergens", "soy_allergy": "allergens",
    "sesame_allergy": "allergens", "fish_shellfish_allergy": "allergens",
    "multiple_food_allergy": "allergens", "oral_immunotherapy_allergy": "allergens",
    "early_allergen_introduction": "allergens", "allergy_prevention_diet": "allergens",
    "eczema_food_allergy": "allergens", "food_allergy_anaphylaxis": "allergens",
    # feeding
    "complementary_feeding": "feeding", "breastfeeding": "feeding", "infant_formula": "feeding",
    "baby_led_weaning": "feeding", "responsive_feeding": "feeding", "donor_breast_milk": "feeding",
    "mixed_feeding": "feeding", "formula_preparation_safety": "feeding",
    "extended_breastfeeding": "feeding", "breastfeeding_difficulties": "feeding",
    "preterm_infant_nutrition": "feeding",
    # nutrition
    "iron_deficiency": "nutrition", "vitamin_d": "nutrition", "omega3_dha": "nutrition",
    "zinc_infant": "nutrition", "calcium_bone_infant": "nutrition", "iodine_infant": "nutrition",
    "folate_infant": "nutrition", "vitamin_a_infant": "nutrition", "vitamin_b12_infant": "nutrition",
    "vitamin_k_infant": "nutrition", "choline_infant": "nutrition",
    "probiotics_infant": "nutrition", "prebiotics_infant": "nutrition",
    # foods
    "vegetable_introduction": "foods", "fruit_introduction": "foods", "meat_introduction": "foods",
    "fish_introduction": "foods", "dairy_introduction": "foods", "legume_introduction": "foods",
    "whole_grain_infant": "foods", "organic_baby_food": "foods", "sugar_salt_babies": "foods",
    "ultra_processed_infant": "foods", "commercial_baby_food": "foods", "plant_based_infant": "foods",
    # gut
    "gut_microbiome": "gut", "infant_colic": "gut", "infant_constipation": "gut",
    "infant_reflux": "gut", "gut_dysbiosis_infant": "gut", "food_texture_progression": "gut",
    # development
    "infant_growth_faltering": "development", "childhood_obesity_diet": "development",
    "stunting_wasting": "development", "brain_development_nutrition": "development",
    "catch_up_growth": "development", "dental_health_infant": "development",
    "toddler_milk_drinks": "development",
    # behaviour
    "food_neophobia": "behaviour", "picky_eating": "behaviour", "feeding_difficulties": "behaviour",
    "appetite_regulation": "behaviour", "flavor_learning": "behaviour",
    "mealtime_behaviour": "behaviour", "division_of_responsibility": "behaviour",
    # maternal
    "maternal_diet_breastmilk": "maternal", "maternal_nutrition_pregnancy": "maternal",
    "prenatal_allergy_prevention": "maternal", "gestational_diabetes_feeding": "maternal",
    "maternal_microbiome": "maternal", "prenatal_omega3": "maternal",
    "maternal_iodine_pregnancy": "maternal", "maternal_anaemia_infant": "maternal",
    # special
    "low_birth_weight_feeding": "special", "celiac_disease_infant": "special",
    "fpies": "special", "eosinophilic_esophagitis": "special", "cleft_palate_feeding": "special",
    "downs_syndrome_feeding": "special", "immune_development_diet": "special",
    "fortified_complementary_foods": "special",
    # safety
    "heavy_metals_baby_food": "safety", "pesticides_infant_food": "safety",
    "nitrates_baby_food": "safety", "microplastics_formula": "safety",
    "bpa_packaging_infant": "safety", "food_safety_preparation": "safety",
    # socioeconomic
    "food_insecurity_infant": "socioeconomic", "cultural_complementary_feeding": "socioeconomic",
    "global_malnutrition_infant": "socioeconomic", "baby_food_marketing": "socioeconomic",
    "baby_food_labelling": "socioeconomic", "socioeconomic_infant_diet": "socioeconomic",
    "sleep_feeding_infant": "socioeconomic", "screen_time_feeding": "socioeconomic",
}

# Maps primary_field → galaxy group (fallback when AI enrichment has run)
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

    # worksByDecade as array of {decade, works_count} — required by the frontend
    decade_counts = {}
    for r in rows:
        if r["year"]:
            decade = (r["year"] // 10) * 10
            decade_counts[decade] = decade_counts.get(decade, 0) + 1
    works_by_decade = [
        {"decade": d, "works_count": c}
        for d, c in sorted(decade_counts.items())
    ]

    # Group: prefer topic map, fall back to AI primary field mapping
    group = TOPIC_GROUP_MAP.get(topic_key)
    if not group:
        field_counts = {}
        for r in rows:
            f = r["AI_primary_field"] or "Unassigned"
            field_counts[f] = field_counts.get(f, 0) + 1
        dominant_field = max(field_counts, key=field_counts.get) if field_counts else "Unassigned"
        group = FIELD_TO_GROUP.get(dominant_field, "general")

    cfg = PREDEFINED_TOPICS.get(topic_key, {})
    display_name = cfg.get("name") or topic_name(topic_key)
    icon_category = TOPIC_ICON_MAP.get(topic_key, "general")

    return {
        "id": topic_key,
        "name": display_name,
        "group": group,
        "primaryField": cfg.get("food_type_hint", "general"),
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


def load_topic_counts(data_dir):
    path = os.path.join(data_dir, "topic_counts.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def make_stub_node(topic_key, topic_counts):
    cfg = PREDEFINED_TOPICS.get(topic_key, {})
    oac = topic_counts.get(topic_key, 0)
    return {
        "id": topic_key,
        "name": cfg.get("name") or topic_name(topic_key),
        "group": TOPIC_GROUP_MAP.get(topic_key, "general"),
        "primaryField": cfg.get("food_type_hint", "general"),
        "totalWorksCount": 0,
        "totalOpenAlexCount": oac,
        "iconCategory": TOPIC_ICON_MAP.get(topic_key, "general"),
        "hasPapers": False,
        "nodesFile": f"data/{topic_key}/nodes.json",
        "edgesFile": f"data/{topic_key}/edges.json",
        "worksByDecade": [],
        "yearRange": [2000, 2024],
    }


def build_universe(data_dir, out_dir):
    topic_counts = load_topic_counts(data_dir)
    dbs = sorted(glob.glob(os.path.join(data_dir, "papers_*.db")))

    print(f"[build] Found {len(dbs)} databases")
    galaxy_nodes = []
    processed = set()

    for db_path in dbs:
        key = topic_key_from_path(db_path)
        processed.add(key)
        print(f"[build] Processing {key}...")
        node = export_topic(key, db_path, out_dir)
        if node:
            node["totalOpenAlexCount"] = topic_counts.get(key, node["totalWorksCount"])
            galaxy_nodes.append(node)
        else:
            # DB exists but is empty — include as stub so it appears in the map
            stub = make_stub_node(key, topic_counts)
            galaxy_nodes.append(stub)
            print(f"  [stub] {key}: empty DB, {stub['totalOpenAlexCount']:,} in OpenAlex")

    # Add any predefined topics with no DB at all
    for key in PREDEFINED_TOPICS:
        if key not in processed:
            stub = make_stub_node(key, topic_counts)
            galaxy_nodes.append(stub)
            print(f"  [stub] {key}: no DB, {stub['totalOpenAlexCount']:,} in OpenAlex")

    universe = {
        "version": 1,
        "description": "Map of Baby Food Science — evidence-based nutrition research",
        "nodes": galaxy_nodes,
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
