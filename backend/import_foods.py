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
EMAIL = os.environ.get("OPENALEX_EMAIL", "tom.hirsch3000@gmail.com")

# ── Predefined foods with OpenAlex queries ────────────────────────────────────
# Each query targets: this food + infant/child context
PREDEFINED_FOODS = {

    # ── VEGETABLES ───────────────────────────────────────────────────────────
    "broccoli":         {"name": "Broccoli",           "query": "broccoli infant child nutrition",                   "icon_category": "broccoli",        "group": "vegetables"},
    "carrot":           {"name": "Carrot",              "query": "carrot infant child nutrition",                     "icon_category": "carrot",          "group": "vegetables"},
    "sweet_potato":     {"name": "Sweet Potato",        "query": "sweet potato yam infant child nutrition",           "icon_category": "sweet-potato",    "group": "vegetables"},
    "spinach":          {"name": "Spinach",             "query": "spinach infant child nutrition",                    "icon_category": "spinach",         "group": "vegetables"},
    "pea":              {"name": "Peas",                "query": "pea green pea infant child nutrition",              "icon_category": "pea",             "group": "vegetables"},
    "avocado":          {"name": "Avocado",             "query": "avocado infant child nutrition",                    "icon_category": "avocado",         "group": "vegetables"},
    "tomato":           {"name": "Tomato",              "query": "tomato infant child nutrition",                     "icon_category": "tomato",          "group": "vegetables"},
    "zucchini":         {"name": "Zucchini",            "query": "zucchini courgette infant child nutrition",         "icon_category": "zucchini",        "group": "vegetables"},
    "cauliflower":      {"name": "Cauliflower",         "query": "cauliflower infant child nutrition",                "icon_category": "cauliflower",     "group": "vegetables"},
    "beetroot":         {"name": "Beetroot",            "query": "beetroot beet infant child nutrition",              "icon_category": "beetroot",        "group": "vegetables"},
    "parsnip":          {"name": "Parsnip",             "query": "parsnip infant child nutrition",                    "icon_category": "parsnip",         "group": "vegetables"},
    "butternut_squash": {"name": "Butternut Squash",    "query": "butternut squash infant child nutrition",           "icon_category": "butternut-squash","group": "vegetables"},
    "green_bean":       {"name": "Green Bean",          "query": "green bean infant child nutrition",                 "icon_category": "green-bean",      "group": "vegetables"},
    "kale":             {"name": "Kale",                "query": "kale infant child nutrition",                       "icon_category": "kale",            "group": "vegetables"},
    "bell_pepper":      {"name": "Bell Pepper",         "query": "bell pepper capsicum infant child nutrition",       "icon_category": "bell-pepper",     "group": "vegetables"},
    "cucumber":         {"name": "Cucumber",            "query": "cucumber infant child nutrition",                   "icon_category": "cucumber",        "group": "vegetables"},
    "leek":             {"name": "Leek",                "query": "leek infant child nutrition",                       "icon_category": "leek",            "group": "vegetables"},

    # ── FRUITS ───────────────────────────────────────────────────────────────
    "apple":            {"name": "Apple",               "query": "apple infant child nutrition",                      "icon_category": "apple",           "group": "fruits"},
    "banana":           {"name": "Banana",              "query": "banana infant child nutrition",                     "icon_category": "banana",          "group": "fruits"},
    "mango":            {"name": "Mango",               "query": "mango infant child nutrition",                      "icon_category": "mango",           "group": "fruits"},
    "strawberry":       {"name": "Strawberry",          "query": "strawberry infant child nutrition",                 "icon_category": "strawberry",      "group": "fruits"},
    "blueberry":        {"name": "Blueberry",           "query": "blueberry infant child nutrition",                  "icon_category": "blueberry",       "group": "fruits"},
    "pear":             {"name": "Pear",                "query": "pear infant child nutrition",                       "icon_category": "pear",            "group": "fruits"},
    "orange":           {"name": "Orange",              "query": "orange citrus infant child nutrition",              "icon_category": "orange-fruit",    "group": "fruits"},
    "grape":            {"name": "Grape",               "query": "grape infant child nutrition",                      "icon_category": "grape",           "group": "fruits"},
    "watermelon":       {"name": "Watermelon",          "query": "watermelon infant child nutrition",                 "icon_category": "watermelon",      "group": "fruits"},
    "kiwi":             {"name": "Kiwi",                "query": "kiwi kiwifruit infant child nutrition",             "icon_category": "kiwi",            "group": "fruits"},
    "papaya":           {"name": "Papaya",              "query": "papaya pawpaw infant child nutrition",              "icon_category": "papaya",          "group": "fruits"},
    "peach":            {"name": "Peach",               "query": "peach infant child nutrition",                      "icon_category": "peach",           "group": "fruits"},
    "plum":             {"name": "Plum",                "query": "plum infant child nutrition",                       "icon_category": "plum",            "group": "fruits"},
    "raspberry":        {"name": "Raspberry",           "query": "raspberry infant child nutrition",                  "icon_category": "raspberry",       "group": "fruits"},
    "apricot":          {"name": "Apricot",             "query": "apricot infant child nutrition",                    "icon_category": "apricot",         "group": "fruits"},

    # ── PROTEINS ─────────────────────────────────────────────────────────────
    "chicken":          {"name": "Chicken",             "query": "chicken poultry infant child nutrition",            "icon_category": "chicken-meat",    "group": "proteins"},
    "beef":             {"name": "Beef",                "query": "beef infant child nutrition",                       "icon_category": "beef",            "group": "proteins"},
    "salmon":           {"name": "Salmon",              "query": "salmon infant child nutrition",                     "icon_category": "salmon-fish",     "group": "proteins"},
    "sardine":          {"name": "Sardine",             "query": "sardine oily fish infant child nutrition",          "icon_category": "sardine",         "group": "proteins"},
    "egg":              {"name": "Egg",                 "query": "egg infant child nutrition",                        "icon_category": "egg-food",        "group": "proteins"},
    "lentil":           {"name": "Lentil",              "query": "lentil infant child nutrition",                     "icon_category": "lentil",          "group": "proteins"},
    "tuna":             {"name": "Tuna",                "query": "tuna infant child nutrition",                       "icon_category": "tuna-fish",       "group": "proteins"},
    "tofu":             {"name": "Tofu",                "query": "tofu bean curd infant child nutrition",             "icon_category": "tofu",            "group": "proteins"},
    "cod":              {"name": "Cod",                 "query": "cod white fish infant child nutrition",             "icon_category": "cod-fish",        "group": "proteins"},
    "tempeh":           {"name": "Tempeh",              "query": "tempeh infant child nutrition",                     "icon_category": "tempeh",          "group": "proteins"},

    # ── DAIRY ────────────────────────────────────────────────────────────────
    "cows_milk":        {"name": "Cow's Milk",          "query": "cow milk infant child nutrition",                   "icon_category": "cows-milk",       "group": "dairy"},
    "yogurt":           {"name": "Yogurt",              "query": "yogurt yoghurt infant child nutrition",             "icon_category": "yogurt-food",     "group": "dairy"},
    "cheese":           {"name": "Cheese",              "query": "cheese infant child nutrition",                     "icon_category": "cheese-food",     "group": "dairy"},
    "breast_milk":      {"name": "Breast Milk",         "query": "breast milk human milk infant nutrition",           "icon_category": "breast-milk-f",   "group": "dairy"},
    "butter":           {"name": "Butter",              "query": "butter infant child nutrition",                     "icon_category": "butter",          "group": "dairy"},
    "kefir":            {"name": "Kefir",               "query": "kefir infant child nutrition",                      "icon_category": "kefir",           "group": "dairy"},

    # ── GRAINS ───────────────────────────────────────────────────────────────
    "oats":             {"name": "Oats",                "query": "oats oatmeal infant child nutrition",               "icon_category": "oats-food",       "group": "grains"},
    "rice":             {"name": "Rice",                "query": "rice infant child nutrition",                       "icon_category": "rice-food",       "group": "grains"},
    "wheat":            {"name": "Wheat",               "query": "wheat infant child nutrition",                      "icon_category": "wheat-food",      "group": "grains"},
    "quinoa":           {"name": "Quinoa",              "query": "quinoa infant child nutrition",                     "icon_category": "quinoa",          "group": "grains"},
    "corn":             {"name": "Corn / Maize",        "query": "corn maize infant child nutrition",                 "icon_category": "corn",            "group": "grains"},
    "barley":           {"name": "Barley",              "query": "barley infant child nutrition",                     "icon_category": "barley",          "group": "grains"},
    "millet":           {"name": "Millet",              "query": "millet infant child nutrition",                     "icon_category": "millet",          "group": "grains"},
    "bread":            {"name": "Bread",               "query": "bread infant child nutrition",                      "icon_category": "bread",           "group": "grains"},
    "buckwheat":        {"name": "Buckwheat",           "query": "buckwheat infant child nutrition",                  "icon_category": "buckwheat",       "group": "grains"},

    # ── LEGUMES & NUTS ───────────────────────────────────────────────────────
    "chickpea":         {"name": "Chickpea",            "query": "chickpea garbanzo infant child nutrition",          "icon_category": "chickpea",        "group": "legumes"},
    "kidney_bean":      {"name": "Kidney Bean",         "query": "kidney bean infant child nutrition",                "icon_category": "kidney-bean",     "group": "legumes"},
    "peanut":           {"name": "Peanut",              "query": "peanut groundnut infant child nutrition",           "icon_category": "peanut-food",     "group": "legumes"},
    "soy":              {"name": "Soy",                 "query": "soy soybean infant child nutrition",                "icon_category": "soy-food",        "group": "legumes"},
    "almond":           {"name": "Almond",              "query": "almond infant child nutrition",                     "icon_category": "almond",          "group": "legumes"},
    "black_bean":       {"name": "Black Bean",          "query": "black bean infant child nutrition",                 "icon_category": "black-bean",      "group": "legumes"},
    "cashew":           {"name": "Cashew",              "query": "cashew infant child nutrition",                     "icon_category": "cashew",          "group": "legumes"},
    "walnut":           {"name": "Walnut",              "query": "walnut infant child nutrition",                     "icon_category": "walnut",          "group": "legumes"},
    "sunflower_seeds":  {"name": "Sunflower Seeds",     "query": "sunflower seed infant child nutrition",             "icon_category": "sunflower-seeds", "group": "legumes"},
    "pumpkin_seeds":    {"name": "Pumpkin Seeds",       "query": "pumpkin seed infant child nutrition",               "icon_category": "pumpkin-seeds",   "group": "legumes"},
    "tahini":           {"name": "Tahini",              "query": "tahini sesame infant child nutrition",              "icon_category": "tahini",          "group": "legumes"},

    # ── FATS & OILS ──────────────────────────────────────────────────────────
    "olive_oil":        {"name": "Olive Oil",           "query": "olive oil infant child nutrition",                  "icon_category": "olive-oil",       "group": "fats"},
    "coconut_oil":      {"name": "Coconut Oil",         "query": "coconut oil infant child nutrition",                "icon_category": "coconut-oil",     "group": "fats"},
    "flaxseed":         {"name": "Flaxseed",            "query": "flaxseed linseed infant child nutrition",           "icon_category": "flaxseed",        "group": "fats"},
    "chia_seed":        {"name": "Chia Seed",           "query": "chia seed infant child nutrition",                  "icon_category": "chia-seed",       "group": "fats"},
    "ghee":             {"name": "Ghee",                "query": "ghee clarified butter infant child nutrition",      "icon_category": "ghee",            "group": "fats"},
    "hemp_seed":        {"name": "Hemp Seed",           "query": "hemp seed infant child nutrition",                  "icon_category": "hemp-seed",       "group": "fats"},

    # ── FUNCTIONAL ───────────────────────────────────────────────────────────
    "probiotic_food":   {"name": "Probiotic Foods",     "query": "probiotic infant child nutrition",                  "icon_category": "probiotic-food",  "group": "functional"},
    "prebiotic_food":   {"name": "Prebiotic Foods",     "query": "prebiotic infant child nutrition",                  "icon_category": "prebiotic-food",  "group": "functional"},
    "dark_chocolate":   {"name": "Dark Chocolate / Cocoa", "query": "cocoa chocolate infant child nutrition",         "icon_category": "dark-chocolate",  "group": "functional"},
    "herbs_spices":     {"name": "Herbs & Spices",      "query": "herbs spices infant child nutrition",               "icon_category": "herbs-spices",    "group": "functional"},
    "turmeric":         {"name": "Turmeric",            "query": "turmeric curcumin infant child nutrition",          "icon_category": "turmeric",        "group": "functional"},
    "ginger":           {"name": "Ginger",              "query": "ginger infant child nutrition",                     "icon_category": "ginger",          "group": "functional"},
    "fortified_cereal": {"name": "Fortified Cereal",    "query": "fortified cereal infant child nutrition",           "icon_category": "fortified-cereal","group": "functional"},

    # ── MEAT ─────────────────────────────────────────────────────────────────
    "turkey":           {"name": "Turkey",              "query": "turkey infant child nutrition",                     "icon_category": "turkey-meat",     "group": "meat"},
    "lamb":             {"name": "Lamb",                "query": "lamb infant child nutrition",                       "icon_category": "lamb-meat",       "group": "meat"},
    "pork":             {"name": "Pork",                "query": "pork infant child nutrition",                       "icon_category": "pork-meat",       "group": "meat"},
    "duck":             {"name": "Duck",                "query": "duck infant child nutrition",                       "icon_category": "duck-meat",       "group": "meat"},
    "venison":          {"name": "Venison",             "query": "venison deer meat infant child nutrition",          "icon_category": "venison",         "group": "meat"},
    "rabbit":           {"name": "Rabbit",              "query": "rabbit infant child nutrition",                     "icon_category": "rabbit-meat",     "group": "meat"},

    # ── SWEETS ───────────────────────────────────────────────────────────────
    "dates":            {"name": "Dates",               "query": "dates infant child nutrition",                      "icon_category": "dates-fruit",     "group": "sweets"},
    "raisins":          {"name": "Raisins",             "query": "raisins dried grapes infant child nutrition",       "icon_category": "raisins",         "group": "sweets"},
    "honey":            {"name": "Honey",               "query": "honey infant child nutrition",                      "icon_category": "honey",           "group": "sweets"},
    "maple_syrup":      {"name": "Maple Syrup",         "query": "maple syrup infant child nutrition",                "icon_category": "maple-syrup",     "group": "sweets"},
    "rice_cake":        {"name": "Rice Cake",           "query": "rice cake infant child nutrition",                  "icon_category": "rice-cake",       "group": "sweets"},
    "fruit_puree":      {"name": "Fruit Puree / Pouch", "query": "fruit puree infant child nutrition",                "icon_category": "fruit-puree",     "group": "sweets"},

    # ── DRINKS ───────────────────────────────────────────────────────────────
    "water":            {"name": "Water",               "query": "water infant child nutrition",                      "icon_category": "water-drink",     "group": "drinks"},
    "formula_milk":     {"name": "Formula Milk",        "query": "infant formula milk nutrition",                     "icon_category": "formula-milk",    "group": "drinks"},
    "fruit_juice":      {"name": "Fruit Juice",         "query": "fruit juice infant child nutrition",                "icon_category": "fruit-juice",     "group": "drinks"},
    "coconut_water":    {"name": "Coconut Water",       "query": "coconut water infant child nutrition",              "icon_category": "coconut-water",   "group": "drinks"},
    "herbal_tea":       {"name": "Herbal Tea",          "query": "herbal tea infant child nutrition",                 "icon_category": "herbal-tea",      "group": "drinks"},
}

# Group ordering for layout
FOOD_GROUP_ORDER = [
    "vegetables", "fruits", "meat", "proteins", "dairy",
    "grains", "legumes", "fats", "functional", "sweets", "drinks",
]


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


def _params_with_email(params: dict) -> dict:
    """OpenAlex routes requests with a real mailto to the high-rate polite pool."""
    return {**params, "mailto": EMAIL}


class BudgetExhaustedError(Exception):
    """Raised when the OpenAlex daily credit budget is exhausted."""
    def __init__(self, retry_after_secs):
        self.retry_after_secs = retry_after_secs
        hrs = retry_after_secs / 3600
        super().__init__(
            f"OpenAlex daily budget exhausted. Resets in {retry_after_secs}s "
            f"({hrs:.1f}h). Run again after midnight UTC."
        )


def _parse_429(response):
    """Extract (is_budget_exhausted, wait_seconds) from a 429 response."""
    # Try JSON body first — OpenAlex budget errors carry retryAfter in the body
    try:
        body = response.json()
        if "dailyRemainingUsd" in body or "creditsRemaining" in body:
            # Budget exhaustion — retryAfter is seconds until midnight UTC
            return True, int(body.get("retryAfter", 3600))
        body_wait = body.get("retryAfter")
        if body_wait:
            return False, int(body_wait)
    except Exception:
        pass

    # Fall back to Retry-After header
    header = response.headers.get("Retry-After")
    if header:
        try:
            value = int(header)
            # Unix timestamps are > 1 billion; durations are not
            if value > 1_000_000_000:
                wait = max(1, value - int(time.time()))
            else:
                wait = value
            return False, min(wait, 120)
        except ValueError:
            pass

    return False, 0


HARD_PAUSE_AFTER = 4   # switch to hard pause after this many fast retries
HARD_PAUSE_SECS  = 180 # 3 minutes


def _get_with_retry(url, params, max_retries=8, base_delay=5):
    """GET with retries on 429/5xx.

    Strategy:
      attempts 1–4 : exponential back-off (5s, 10s, 20s, 40s)
      attempts 5–8 : hard 3-minute pause each time
    Budget exhaustion (daily credits gone) raises BudgetExhaustedError immediately.
    """
    for attempt in range(max_retries):
        r = requests.get(url, params=_params_with_email(params), headers=_headers(), timeout=30)
        if r.status_code == 429:
            is_budget, wait_secs = _parse_429(r)
            if is_budget:
                raise BudgetExhaustedError(wait_secs)
            if attempt < HARD_PAUSE_AFTER:
                backoff = base_delay * (2 ** attempt)   # 5, 10, 20, 40s
                wait = max(wait_secs, backoff)
                print(f"\n  [rate-limit] 429 — waiting {wait}s (attempt {attempt + 1}/{max_retries})...")
            else:
                wait = HARD_PAUSE_SECS
                print(f"\n  [rate-limit] 429 — hard pause {wait}s ({attempt + 1}/{max_retries})...")
            time.sleep(wait)
            continue
        if r.status_code >= 500 and attempt < max_retries - 1:
            wait = base_delay * (2 ** min(attempt, HARD_PAUSE_AFTER - 1))
            print(f"\n  [server-error] {r.status_code} — waiting {wait}s...")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r
    r.raise_for_status()
    return r


def fetch_food_count(food_key):
    cfg = PREDEFINED_FOODS[food_key]
    params = {
        "search": cfg["query"],
        "filter": "type:article,has_abstract:true",
        "per-page": 1,
        "select": "id",
    }
    try:
        r = _get_with_retry(f"{OPENALEX_BASE}/works", params)
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
        time.sleep(0.5)  # polite pool allows ~2 req/s; stay well under

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
        r = _get_with_retry(f"{OPENALEX_BASE}/works", params)
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
        time.sleep(0.5)  # stay within polite pool rate limit
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
