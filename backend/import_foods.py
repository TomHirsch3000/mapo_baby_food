#!/usr/bin/env python3
"""
import_foods.py — Fetches papers from OpenAlex for specific foods and stores
them in per-food SQLite databases (food_papers_<food>.db).

Usage:
    python import_foods.py --food broccoli --max 300
    python import_foods.py --list-foods
    python import_foods.py --counts-only
"""

import argparse
import json
import os
import sqlite3
import sys
import time

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..', 'data'))
FOOD_COUNTS_PATH = os.path.join(DATA_DIR, "food_counts.json")

OPENALEX_BASE = "https://api.openalex.org"
EMAIL = os.environ.get("OPENALEX_EMAIL", "research@example.com")

# ── Predefined foods with OpenAlex queries ────────────────────────────────────
# Each query targets: this food + infant/child context
PREDEFINED_FOODS = {

    # ── VEGETABLES (9) ───────────────────────────────────────────────────────
    "broccoli": {
        "name": "Broccoli",
        "query": "broccoli infant child vegetable introduction nutrition cancer glucosinolate",
        "icon_category": "broccoli",
        "group": "vegetables",
    },
    "carrot": {
        "name": "Carrot",
        "query": "carrot infant child vegetable beta-carotene vitamin A introduction puree",
        "icon_category": "carrot",
        "group": "vegetables",
    },
    "sweet_potato": {
        "name": "Sweet Potato",
        "query": "sweet potato infant complementary feeding beta-carotene vitamin A puree",
        "icon_category": "sweet-potato",
        "group": "vegetables",
    },
    "spinach": {
        "name": "Spinach",
        "query": "spinach infant child leafy greens iron nitrate complementary food",
        "icon_category": "spinach",
        "group": "vegetables",
    },
    "pea": {
        "name": "Peas",
        "query": "pea infant vegetable protein complementary food introduction puree",
        "icon_category": "pea",
        "group": "vegetables",
    },
    "avocado": {
        "name": "Avocado",
        "query": "avocado infant child healthy fat monounsaturated nutrition complementary",
        "icon_category": "avocado",
        "group": "vegetables",
    },
    "tomato": {
        "name": "Tomato",
        "query": "tomato infant child lycopene antioxidant vegetable introduction diet",
        "icon_category": "tomato",
        "group": "vegetables",
    },
    "zucchini": {
        "name": "Zucchini",
        "query": "zucchini courgette infant vegetable complementary feeding puree nutrition",
        "icon_category": "zucchini",
        "group": "vegetables",
    },
    "cauliflower": {
        "name": "Cauliflower",
        "query": "cauliflower infant child vegetable introduction nutrition glucosinolate",
        "icon_category": "cauliflower",
        "group": "vegetables",
    },

    # ── FRUITS (9) ───────────────────────────────────────────────────────────
    "apple": {
        "name": "Apple",
        "query": "apple infant fruit introduction puree juice complementary feeding polyphenol",
        "icon_category": "apple",
        "group": "fruits",
    },
    "banana": {
        "name": "Banana",
        "query": "banana infant fruit potassium complementary feeding weaning puree",
        "icon_category": "banana",
        "group": "fruits",
    },
    "mango": {
        "name": "Mango",
        "query": "mango infant child tropical fruit vitamin C complementary feeding developing countries",
        "icon_category": "mango",
        "group": "fruits",
    },
    "strawberry": {
        "name": "Strawberry",
        "query": "strawberry infant child berry vitamin C antioxidant introduction allergy",
        "icon_category": "strawberry",
        "group": "fruits",
    },
    "blueberry": {
        "name": "Blueberry",
        "query": "blueberry infant child anthocyanin antioxidant cognitive development brain",
        "icon_category": "blueberry",
        "group": "fruits",
    },
    "pear": {
        "name": "Pear",
        "query": "pear infant fruit introduction complementary feeding fibre constipation",
        "icon_category": "pear",
        "group": "fruits",
    },
    "orange": {
        "name": "Orange",
        "query": "orange infant citrus fruit vitamin C complementary feeding introduction",
        "icon_category": "orange-fruit",
        "group": "fruits",
    },
    "grape": {
        "name": "Grape",
        "query": "grape infant child fruit resveratrol polyphenol juice choking hazard",
        "icon_category": "grape",
        "group": "fruits",
    },
    "watermelon": {
        "name": "Watermelon",
        "query": "watermelon infant child fruit lycopene hydration complementary feeding",
        "icon_category": "watermelon",
        "group": "fruits",
    },

    # ── PROTEINS / MEAT (6) ──────────────────────────────────────────────────
    "chicken": {
        "name": "Chicken",
        "query": "chicken infant child meat protein iron complementary feeding introduction poultry",
        "icon_category": "chicken-meat",
        "group": "proteins",
    },
    "beef": {
        "name": "Beef",
        "query": "beef infant child meat protein iron haem complementary feeding red meat",
        "icon_category": "beef",
        "group": "proteins",
    },
    "salmon": {
        "name": "Salmon",
        "query": "salmon infant child fish omega-3 DHA introduction complementary feeding",
        "icon_category": "salmon-fish",
        "group": "proteins",
    },
    "sardine": {
        "name": "Sardine",
        "query": "sardine oily fish infant child omega-3 calcium complementary feeding introduction",
        "icon_category": "sardine",
        "group": "proteins",
    },
    "egg": {
        "name": "Egg",
        "query": "egg infant choline protein introduction complementary feeding allergy prevention",
        "icon_category": "egg-food",
        "group": "proteins",
    },
    "lentil": {
        "name": "Lentil",
        "query": "lentil infant child legume iron protein plant-based complementary feeding",
        "icon_category": "lentil",
        "group": "proteins",
    },

    # ── DAIRY (4) ────────────────────────────────────────────────────────────
    "cows_milk": {
        "name": "Cow's Milk",
        "query": "cow milk whole infant toddler nutrition calcium allergy introduction timing",
        "icon_category": "cows-milk",
        "group": "dairy",
    },
    "yogurt": {
        "name": "Yogurt",
        "query": "yogurt infant toddler complementary food probiotic calcium introduction dairy",
        "icon_category": "yogurt-food",
        "group": "dairy",
    },
    "cheese": {
        "name": "Cheese",
        "query": "cheese infant child calcium protein complementary feeding sodium salt dairy",
        "icon_category": "cheese-food",
        "group": "dairy",
    },
    "breast_milk": {
        "name": "Breast Milk",
        "query": "breast milk human milk composition nutrition infant immunity bioactive",
        "icon_category": "breast-milk-f",
        "group": "dairy",
    },

    # ── GRAINS & CEREALS (5) ─────────────────────────────────────────────────
    "oats": {
        "name": "Oats",
        "query": "oats infant porridge beta-glucan fibre complementary feeding first food",
        "icon_category": "oats-food",
        "group": "grains",
    },
    "rice": {
        "name": "Rice",
        "query": "rice infant complementary food cereal arsenic introduction porridge nutrition",
        "icon_category": "rice-food",
        "group": "grains",
    },
    "wheat": {
        "name": "Wheat",
        "query": "wheat infant gluten introduction complementary feeding celiac allergy timing",
        "icon_category": "wheat-food",
        "group": "grains",
    },
    "quinoa": {
        "name": "Quinoa",
        "query": "quinoa infant child complete protein amino acid complementary feeding nutrition",
        "icon_category": "quinoa",
        "group": "grains",
    },
    "corn": {
        "name": "Corn / Maize",
        "query": "corn maize infant child complementary food staple developing countries nutrition",
        "icon_category": "corn",
        "group": "grains",
    },

    # ── LEGUMES & NUTS (5) ───────────────────────────────────────────────────
    "chickpea": {
        "name": "Chickpea",
        "query": "chickpea garbanzo infant child protein iron complementary food developing countries",
        "icon_category": "chickpea",
        "group": "legumes",
    },
    "kidney_bean": {
        "name": "Kidney Bean",
        "query": "kidney bean infant child legume protein iron complementary feeding plant-based",
        "icon_category": "kidney-bean",
        "group": "legumes",
    },
    "peanut": {
        "name": "Peanut",
        "query": "peanut infant introduction protein allergy prevention LEAP early exposure",
        "icon_category": "peanut-food",
        "group": "legumes",
    },
    "soy": {
        "name": "Soy",
        "query": "soy infant formula plant-based protein isoflavone allergy complementary",
        "icon_category": "soy-food",
        "group": "legumes",
    },
    "almond": {
        "name": "Almond",
        "query": "almond nut infant child vitamin E healthy fat introduction allergy prevention",
        "icon_category": "almond",
        "group": "legumes",
    },

    # ── FATS & OILS (3) ──────────────────────────────────────────────────────
    "olive_oil": {
        "name": "Olive Oil",
        "query": "olive oil infant child Mediterranean diet monounsaturated fat complementary",
        "icon_category": "olive-oil",
        "group": "fats",
    },
    "coconut_oil": {
        "name": "Coconut Oil",
        "query": "coconut oil infant child medium-chain triglyceride nutrition complementary",
        "icon_category": "coconut-oil",
        "group": "fats",
    },
    "flaxseed": {
        "name": "Flaxseed",
        "query": "flaxseed linseed infant child omega-3 ALA plant-based complementary nutrition",
        "icon_category": "flaxseed",
        "group": "fats",
    },

    # ── FUNCTIONAL / SPECIAL (4) ─────────────────────────────────────────────
    "probiotic_food": {
        "name": "Probiotic Foods",
        "query": "probiotic fermented food infant kefir kimchi gut microbiome lactobacillus bifidobacterium",
        "icon_category": "probiotic-food",
        "group": "functional",
    },
    "prebiotic_food": {
        "name": "Prebiotic Foods",
        "query": "prebiotic fibre infant gut microbiome garlic onion banana oat inulin FOS",
        "icon_category": "prebiotic-food",
        "group": "functional",
    },
    "dark_chocolate": {
        "name": "Dark Chocolate / Cocoa",
        "query": "cocoa dark chocolate child flavonoid antioxidant cognitive iron complementary",
        "icon_category": "dark-chocolate",
        "group": "functional",
    },
    "herbs_spices": {
        "name": "Herbs & Spices",
        "query": "herbs spices infant toddler flavour learning turmeric ginger cinnamon introduction",
        "icon_category": "herbs-spices",
        "group": "functional",
    },
}

# Group ordering for layout
FOOD_GROUP_ORDER = ["vegetables", "fruits", "proteins", "dairy", "grains", "legumes", "fats", "functional"]


# ── Database helpers ──────────────────────────────────────────────────────────

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
            food_key TEXT,
            food_name TEXT,
            food_group TEXT,
            icon_category TEXT,
            paper_nature TEXT,
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


# ── OpenAlex helpers ──────────────────────────────────────────────────────────

def _headers():
    return {"User-Agent": f"mapo-baby-food/1.0 (mailto:{EMAIL})"}


def fetch_food_count(food_key):
    cfg = PREDEFINED_FOODS[food_key]
    params = {
        "search": cfg["query"],
        "filter": "type:article,has_abstract:true",
        "per-page": 1,
        "select": "id",
    }
    try:
        r = requests.get(f"{OPENALEX_BASE}/works", params=params, headers=_headers(), timeout=30)
        r.raise_for_status()
        return r.json().get("meta", {}).get("count", 0)
    except Exception as e:
        print(f"  [warn] count fetch failed for {food_key}: {e}")
        return 0


def fetch_all_food_counts(out_path=None):
    """Lightweight sweep: one API call per food → food_counts.json."""
    if out_path is None:
        out_path = FOOD_COUNTS_PATH
    existing = {}
    if os.path.exists(out_path):
        with open(out_path) as f:
            existing = json.load(f)

    counts = dict(existing)
    total = len(PREDEFINED_FOODS)
    for i, key in enumerate(PREDEFINED_FOODS, 1):
        count = fetch_food_count(key)
        counts[key] = count
        print(f"  [{i:3d}/{total}] {key:35s} {count:>8,d}")
        time.sleep(0.15)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(counts, f, indent=2)
    print(f"\nSaved food counts → {out_path}")
    return counts


def fetch_works(query, max_results=300):
    params = {
        "search": query,
        "filter": "type:article,has_abstract:true",
        "per-page": 200,
        "cursor": "*",
        "select": (
            "id,title,abstract_inverted_index,publication_year,publication_date,"
            "cited_by_count,authorships,primary_location,referenced_works,topics,type"
        ),
    }
    fetched = []
    while len(fetched) < max_results:
        r = requests.get(f"{OPENALEX_BASE}/works", params=params, headers=_headers(), timeout=30)
        r.raise_for_status()
        data = r.json()
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


def parse_paper(work, food_key):
    cfg = PREDEFINED_FOODS[food_key]
    paper_id = work["id"].replace("https://openalex.org/", "")
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))

    authors = work.get("authorships", [])
    author_names = [a["author"]["display_name"] for a in authors if a.get("author") and a["author"].get("display_name")]
    institutions = []
    for a in authors:
        for inst in a.get("institutions", []):
            if inst.get("display_name"):
                institutions.append(inst["display_name"])

    work_type = work.get("type", "")
    topics = [t.get("display_name", "") for t in (work.get("topics") or [])]
    joined = " ".join(topics).lower()

    paper_nature = "review"
    if any(k in joined for k in ["trial", "rct", "randomized"]):
        paper_nature = "clinical_trial"
    elif any(k in joined for k in ["cohort", "longitudinal", "prospective"]):
        paper_nature = "experimental"
    elif "meta-analysis" in joined:
        paper_nature = "meta_analysis"
    elif abstract and any(k in abstract.lower() for k in ["randomized", "randomised", "placebo"]):
        paper_nature = "clinical_trial"

    study_type = paper_nature if paper_nature != "review" else ("review" if "review" in work_type.lower() else "article")

    primary_loc = work.get("primary_location") or {}
    doi = primary_loc.get("doi", "") or ""
    url = f"https://doi.org/{doi.replace('https://doi.org/', '')}" if doi else ""

    return {
        "paperId": paper_id,
        "title": work.get("title", ""),
        "abstract": abstract,
        "year": work.get("publication_year"),
        "publicationDate": work.get("publication_date", ""),
        "cited_by_count": work.get("cited_by_count", 0),
        "all_author_names": "; ".join(author_names),
        "first_author_name": author_names[0] if author_names else "Unknown",
        "all_institution_names": "; ".join(dict.fromkeys(institutions)),
        "food_key": food_key,
        "food_name": cfg["name"],
        "food_group": cfg["group"],
        "icon_category": cfg["icon_category"],
        "paper_nature": paper_nature,
        "study_type": study_type,
        "doi": doi,
        "url": url,
        "raw_json": json.dumps(work),
    }, [r.replace("https://openalex.org/", "") for r in work.get("referenced_works", [])]


# ── Import entry point ────────────────────────────────────────────────────────

def import_food(food_key, max_results=300, min_citations=0):
    if food_key not in PREDEFINED_FOODS:
        print(f"[error] Unknown food key: {food_key}")
        print(f"Available: {', '.join(PREDEFINED_FOODS.keys())}")
        sys.exit(1)

    cfg = PREDEFINED_FOODS[food_key]
    os.makedirs(DATA_DIR, exist_ok=True)
    db_path = os.path.join(DATA_DIR, f"food_papers_{food_key}.db")
    print(f"[import] Food:  {cfg['name']}")
    print(f"[import] Query: {cfg['query']}")
    print(f"[import] DB:    {db_path}")

    conn = create_db(db_path)
    existing = {r[0] for r in conn.execute("SELECT paperId FROM papers").fetchall()}
    print(f"[import] Existing papers: {len(existing)}")

    total_count = fetch_food_count(food_key)
    print(f"[import] Total in OpenAlex: {total_count:,}")

    counts = {}
    if os.path.exists(FOOD_COUNTS_PATH):
        with open(FOOD_COUNTS_PATH) as f:
            counts = json.load(f)
    counts[food_key] = total_count
    with open(FOOD_COUNTS_PATH, "w") as f:
        json.dump(counts, f, indent=2)

    works = fetch_works(cfg["query"], max_results=max_results)

    inserted, skipped, citation_pairs = 0, 0, []
    for work in works:
        paper, ref_ids = parse_paper(work, food_key)
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
             food_key, food_name, food_group, icon_category,
             paper_nature, study_type, doi, url, raw_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            paper["paperId"], paper["title"], paper["abstract"], paper["year"],
            paper["publicationDate"], paper["cited_by_count"],
            paper["all_author_names"], paper["first_author_name"],
            paper["all_institution_names"],
            paper["food_key"], paper["food_name"], paper["food_group"], paper["icon_category"],
            paper["paper_nature"], paper["study_type"], paper["doi"], paper["url"],
            paper["raw_json"],
        ))
        existing.add(paper["paperId"])
        citation_pairs.extend((paper["paperId"], r) for r in ref_ids)
        inserted += 1

    conn.executemany(
        "INSERT OR IGNORE INTO citations (source, target) VALUES (?,?)",
        citation_pairs
    )
    conn.commit()
    conn.close()

    print(f"[import] Done: {inserted} inserted, {skipped} skipped")
    return inserted


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Import baby food papers from OpenAlex")
    parser.add_argument("--food", help="Food key to import (e.g. broccoli)")
    parser.add_argument("--max", type=int, default=300, help="Max papers to fetch")
    parser.add_argument("--min-citations", type=int, default=0)
    parser.add_argument("--list-foods", action="store_true")
    parser.add_argument("--counts-only", action="store_true", help="Fetch OpenAlex counts without importing papers")
    args = parser.parse_args()

    if args.list_foods:
        for key, cfg in PREDEFINED_FOODS.items():
            print(f"  {key:30s} — {cfg['name']} ({cfg['group']})")
        return

    if args.counts_only:
        fetch_all_food_counts()
        return

    if not args.food:
        parser.error("Provide --food <key> or --list-foods or --counts-only")

    import_food(args.food, max_results=args.max, min_citations=args.min_citations)


if __name__ == "__main__":
    main()
