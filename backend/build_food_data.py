#!/usr/bin/env python3
"""
build_food_data.py — Builds food_universe.json and per-food JSON files from
food_papers_*.db SQLite databases.

Output:
  - frontend/public/food_universe.json
  - frontend/public/food_data/<food_key>/nodes.json
  - frontend/public/food_data/<food_key>/edges.json

Usage:
    python build_food_data.py
    python build_food_data.py --data-dir ../data --out-dir ../frontend/public
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
from import_foods import PREDEFINED_FOODS, FOOD_GROUP_ORDER


def food_key_from_path(db_path):
    return os.path.basename(db_path).replace("food_papers_", "").replace(".db", "")


def open_conn(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def load_food_counts(data_dir):
    path = os.path.join(data_dir, "food_counts.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}


def build_food_node(food_key, conn):
    rows = conn.execute("SELECT year, cited_by_count FROM papers").fetchall()
    if not rows:
        return None

    total = len(rows)
    total_citations = sum(r["cited_by_count"] or 0 for r in rows)
    years = [r["year"] for r in rows if r["year"]]

    decade_counts = {}
    for r in rows:
        if r["year"]:
            decade = (r["year"] // 10) * 10
            decade_counts[decade] = decade_counts.get(decade, 0) + 1
    works_by_decade = [{"decade": d, "works_count": c} for d, c in sorted(decade_counts.items())]

    cfg = PREDEFINED_FOODS.get(food_key, {})
    return {
        "id": food_key,
        "name": cfg.get("name", food_key.replace("_", " ").title()),
        "group": cfg.get("group", "general"),
        "iconCategory": cfg.get("icon_category", "general"),
        "totalWorksCount": total,
        "totalCitations": total_citations,
        "hasPapers": True,
        "nodesFile": f"food_data/{food_key}/nodes.json",
        "edgesFile": f"food_data/{food_key}/edges.json",
        "worksByDecade": works_by_decade,
        "yearRange": [min(years), max(years)] if years else [2000, 2024],
    }


def build_paper_node(row):
    yr = row["year"]
    if not yr and row["publicationDate"]:
        try:
            yr = int(row["publicationDate"].split("-")[0])
        except Exception:
            yr = 2000

    return {
        "id": row["paperId"],
        "title": row["title"] or "",
        "year": yr,
        "citationCount": row["cited_by_count"] or 0,
        "abstract": row["abstract"] or "",
        "authors": row["all_author_names"] or row["first_author_name"] or "Unknown",
        "institutions": row["all_institution_names"] or "",
        "paperNature": row["paper_nature"],
        "studyType": row["study_type"] or row["paper_nature"],
        "iconCategory": row["icon_category"],
        "foodKey": row["food_key"],
        "foodName": row["food_name"],
        "foodGroup": row["food_group"],
        "doi": row["doi"] or "",
        "url": row["url"] or "",
    }


def export_food(food_key, db_path, out_dir):
    conn = open_conn(db_path)
    try:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        if "papers" not in tables:
            print(f"  [skip] {food_key}: no papers table")
            return None

        rows = conn.execute("SELECT * FROM papers").fetchall()
        if not rows:
            print(f"  [skip] {food_key}: empty")
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

        food_out = os.path.join(out_dir, "food_data", food_key)
        os.makedirs(food_out, exist_ok=True)
        with open(os.path.join(food_out, "nodes.json"), "w") as f:
            json.dump(nodes, f, separators=(",", ":"))
        with open(os.path.join(food_out, "edges.json"), "w") as f:
            json.dump(edges, f, separators=(",", ":"))

        food_node = build_food_node(food_key, conn)
        print(f"  [ok] {food_key}: {len(nodes)} papers, {len(edges)} citations")
        return food_node
    finally:
        conn.close()


def make_stub_node(food_key, food_counts):
    cfg = PREDEFINED_FOODS.get(food_key, {})
    oac = food_counts.get(food_key, 0)
    return {
        "id": food_key,
        "name": cfg.get("name", food_key.replace("_", " ").title()),
        "group": cfg.get("group", "general"),
        "iconCategory": cfg.get("icon_category", "general"),
        "totalWorksCount": 0,
        "totalOpenAlexCount": oac,
        "hasPapers": False,
        "nodesFile": f"food_data/{food_key}/nodes.json",
        "edgesFile": f"food_data/{food_key}/edges.json",
        "worksByDecade": [],
        "yearRange": [2000, 2024],
    }


def build_food_universe(data_dir, out_dir):
    food_counts = load_food_counts(data_dir)
    dbs = sorted(glob.glob(os.path.join(data_dir, "food_papers_*.db")))

    print(f"[build] Found {len(dbs)} food databases")
    food_nodes = []
    processed = set()

    for db_path in dbs:
        key = food_key_from_path(db_path)
        processed.add(key)
        print(f"[build] Processing {key}...")
        node = export_food(key, db_path, out_dir)
        if node:
            node["totalOpenAlexCount"] = food_counts.get(key, node["totalWorksCount"])
            food_nodes.append(node)
        else:
            stub = make_stub_node(key, food_counts)
            food_nodes.append(stub)
            print(f"  [stub] {key}: empty DB")

    # Add any predefined foods with no DB
    for key in PREDEFINED_FOODS:
        if key not in processed:
            stub = make_stub_node(key, food_counts)
            food_nodes.append(stub)
            oac = stub["totalOpenAlexCount"]
            print(f"  [stub] {key}: no DB, {oac:,} in OpenAlex")

    # Sort by group order then name
    group_rank = {g: i for i, g in enumerate(FOOD_GROUP_ORDER)}
    food_nodes.sort(key=lambda n: (group_rank.get(n["group"], 99), n["name"]))

    universe = {
        "version": 1,
        "description": "Map of Baby Food Science — food-level research map",
        "nodes": food_nodes,
    }

    path = os.path.join(out_dir, "food_universe.json")
    with open(path, "w") as f:
        json.dump(universe, f, indent=2)
    print(f"\n[build] food_universe.json written: {path}")
    print(f"[build] {len(food_nodes)} food nodes")


def main():
    parser = argparse.ArgumentParser(description="Build food_universe.json from food SQLite DBs")
    parser.add_argument("--data-dir", default=DATA_DIR)
    parser.add_argument("--out-dir", default=OUT_DIR)
    args = parser.parse_args()
    os.makedirs(args.out_dir, exist_ok=True)
    build_food_universe(args.data_dir, args.out_dir)


if __name__ == "__main__":
    main()
