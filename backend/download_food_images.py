#!/usr/bin/env python3
"""
download_food_images.py — Downloads real food images from Wikipedia for all
predefined foods and saves them as 200×200 JPEG thumbnails.

Output: frontend/public/images/foods/<icon_category>.jpg

Usage:
    python download_food_images.py              # download all missing images
    python download_food_images.py --force      # re-download even if file exists
    python download_food_images.py --food kiwi  # single food key
"""

import argparse
import os
import sys
import time
from io import BytesIO

import requests
from PIL import Image

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.normpath(
    os.path.join(SCRIPT_DIR, '..', 'frontend', 'public', 'images', 'foods')
)

sys.path.insert(0, SCRIPT_DIR)
from import_foods import PREDEFINED_FOODS

IMAGE_SIZE = 200

# Map icon_category → Wikipedia article title to search for
# (override when the default food name gives poor results)
WIKIPEDIA_OVERRIDES = {
    "chicken-meat":    "Chicken as food",
    "beef":            "Beef",
    "salmon-fish":     "Salmon",
    "sardine":         "Sardine",
    "egg-food":        "Egg as food",
    "cows-milk":       "Milk",
    "yogurt-food":     "Yogurt",
    "cheese-food":     "Cheese",
    "breast-milk-f":   "Breastfeeding",
    "oats-food":       "Oat",
    "rice-food":       "Rice",
    "wheat-food":      "Wheat",
    "olive-oil":       "Olive oil",
    "coconut-oil":     "Coconut oil",
    "probiotic-food":  "Probiotic",
    "prebiotic-food":  "Prebiotic",
    "dark-chocolate":  "Dark chocolate",
    "herbs-spices":    "Spice",
    "orange-fruit":    "Orange (fruit)",
    "peanut-food":     "Peanut",
    "soy-food":        "Soybean",
    "sweet-potato":    "Sweet potato",
    "kidney-bean":     "Kidney bean",
    "chickpea":        "Chickpea",
    "tuna-fish":       "Tuna",
    "cod-fish":        "Cod",
    "turkey-meat":     "Turkey meat",
    "lamb-meat":       "Lamb and mutton",
    "pork-meat":       "Pork",
    "duck-meat":       "Duck as food",
    "rabbit-meat":     "Rabbit as food",
    "venison":         "Venison",
    "dates-fruit":     "Date palm",
    "water-drink":     "Drinking water",
    "formula-milk":    "Infant formula",
    "fruit-juice":     "Juice",
    "coconut-water":   "Coconut water",
    "herbal-tea":      "Herbal tea",
    "fortified-cereal":"Breakfast cereal",
    "rice-cake":       "Rice cake",
    "fruit-puree":     "Baby food",
    "maple-syrup":     "Maple syrup",
    "sunflower-seeds": "Sunflower seed",
    "pumpkin-seeds":   "Pumpkin seed",
    "chia-seed":       "Chia seed",
    "hemp-seed":       "Hemp",
    "butternut-squash":"Butternut squash",
    "green-bean":      "Green bean",
    "bell-pepper":     "Bell pepper",
    "black-bean":      "Black turtle bean",
    "buckwheat":       "Buckwheat",
}

# Group images — what to search for each group icon
GROUP_IMAGES = {
    "group-vegetables": "Vegetable",
    "group-fruits":     "Fruit",
    "group-proteins":   "Protein (nutrient)",
    "group-meat":       "Meat",
    "group-dairy":      "Dairy product",
    "group-grains":     "Cereal",
    "group-legumes":    "Legume",
    "group-fats":       "Fat",
    "group-functional": "Functional food",
    "group-sweets":     "Confectionery",
    "group-drinks":     "Drink",
}


def icon_to_wikipedia_title(icon_category: str) -> str:
    if icon_category in WIKIPEDIA_OVERRIDES:
        return WIKIPEDIA_OVERRIDES[icon_category]
    # Derive a reasonable title from the icon_category slug
    return icon_category.replace("-", " ").replace("_", " ").title()


def fetch_wikipedia_thumbnail(title: str, size: int = IMAGE_SIZE) -> str | None:
    """Return the thumbnail URL for a Wikipedia article, or None."""
    url = "https://en.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "titles": title,
        "prop": "pageimages",
        "format": "json",
        "pithumbsize": size,
        "redirects": 1,
    }
    try:
        r = requests.get(url, params=params, timeout=15,
                         headers={"User-Agent": "mapo-baby-food/1.0 image-downloader"})
        r.raise_for_status()
        data = r.json()
        pages = data.get("query", {}).get("pages", {})
        for page in pages.values():
            thumb = page.get("thumbnail", {})
            if thumb and "source" in thumb:
                return thumb["source"]
    except Exception as e:
        print(f"    [warn] Wikipedia API error for '{title}': {e}")
    return None


def download_and_save(img_url: str, out_path: str, size: int = IMAGE_SIZE) -> bool:
    """Download an image, crop to square, resize, and save as JPEG."""
    try:
        r = requests.get(img_url, timeout=20,
                         headers={"User-Agent": "mapo-baby-food/1.0 image-downloader"})
        r.raise_for_status()
        img = Image.open(BytesIO(r.content)).convert("RGB")
        # Centre-crop to square
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top = (h - side) // 2
        img = img.crop((left, top, left + side, top + side))
        img = img.resize((size, size), Image.LANCZOS)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        img.save(out_path, "JPEG", quality=85, optimize=True)
        return True
    except Exception as e:
        print(f"    [warn] download/save error: {e}")
        return False


def download_image(icon_category: str, force: bool = False) -> bool:
    out_path = os.path.join(OUT_DIR, f"{icon_category}.jpg")
    if os.path.exists(out_path) and not force:
        print(f"  [skip] {icon_category} — already exists")
        return True

    title = icon_to_wikipedia_title(icon_category)
    print(f"  [fetch] {icon_category} → '{title}'", end=" ... ", flush=True)
    thumb_url = fetch_wikipedia_thumbnail(title)
    if not thumb_url:
        print("no image found")
        return False
    ok = download_and_save(thumb_url, out_path)
    print("saved" if ok else "failed")
    time.sleep(1.5)
    return ok


def main():
    parser = argparse.ArgumentParser(description="Download food images from Wikipedia")
    parser.add_argument("--force", action="store_true", help="Re-download even if file exists")
    parser.add_argument("--food", help="Download for a single food key only")
    parser.add_argument("--groups", action="store_true", help="Also download group icons")
    args = parser.parse_args()

    # Collect all icon categories
    if args.food:
        if args.food not in PREDEFINED_FOODS:
            print(f"[error] Unknown food key: {args.food}")
            sys.exit(1)
        targets = [(PREDEFINED_FOODS[args.food]["icon_category"], None)]
    else:
        seen = set()
        targets = []
        for cfg in PREDEFINED_FOODS.values():
            ic = cfg["icon_category"]
            if ic not in seen:
                targets.append((ic, cfg["name"]))
                seen.add(ic)
        if args.groups:
            for ic in GROUP_IMAGES:
                targets.append((ic, None))

    print(f"Downloading images for {len(targets)} icon categories → {OUT_DIR}\n")
    ok_count = fail_count = 0

    for i, (icon_cat, name) in enumerate(targets, 1):
        label = f"[{i}/{len(targets)}] {name or icon_cat}"
        print(label)
        if download_image(icon_cat, force=args.force):
            ok_count += 1
        else:
            fail_count += 1

    print(f"\nDone: {ok_count} downloaded, {fail_count} failed.")
    if fail_count:
        print("Run again with --force to retry failed downloads.")


if __name__ == "__main__":
    main()
