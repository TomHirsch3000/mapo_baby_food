#!/usr/bin/env python3
"""
images.py — Shared Wikipedia thumbnail fetching.

Used by download_food_images.py (98 foods) and download_subject_images.py
(claim subjects). Both need the same fetch -> centre-crop -> resize -> JPEG
pipeline, so it lives here once.
"""

import os
import time
from io import BytesIO

import requests
from PIL import Image

WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "mapo-baby-food/1.0 image-downloader"
IMAGE_SIZE = 200
REQUEST_SLEEP = 1.5
MAX_RETRIES = 4


def _get(url, **kwargs):
    """GET with backoff on 429/5xx. Wikimedia throttles hard on bursts, and a
    throttled run silently produces a page full of missing images."""
    delay = 4
    last = None
    for attempt in range(MAX_RETRIES):
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, **kwargs)
        if r.status_code == 429 or r.status_code >= 500:
            last = r
            if attempt < MAX_RETRIES - 1:
                wait = int(r.headers.get("Retry-After") or delay)
                print(f"\n    [rate-limit] {r.status_code} - waiting {wait}s", end="", flush=True)
                time.sleep(wait)
                delay *= 2
                continue
        r.raise_for_status()
        return r
    last.raise_for_status()


def fetch_wikipedia_thumbnail(title, size=IMAGE_SIZE):
    """Thumbnail URL for a Wikipedia article, or None."""
    params = {
        "action": "query",
        "titles": title,
        "prop": "pageimages",
        "format": "json",
        "pithumbsize": size,
        "redirects": 1,
    }
    try:
        r = _get(WIKIPEDIA_API, params=params, timeout=15)
        pages = r.json().get("query", {}).get("pages", {})
        for page in pages.values():
            thumb = page.get("thumbnail", {})
            if thumb and "source" in thumb:
                return thumb["source"]
    except Exception as e:
        print(f"    [warn] Wikipedia API error for '{title}': {e}")
    return None


def download_and_save(img_url, out_path, size=IMAGE_SIZE):
    """Download, centre-crop to square, resize, save as JPEG."""
    try:
        r = _get(img_url, timeout=20)
        img = Image.open(BytesIO(r.content)).convert("RGB")
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


def download_one(key, title, out_dir, force=False, size=IMAGE_SIZE):
    """Fetch the thumbnail for `title` and save it as <out_dir>/<key>.jpg."""
    out_path = os.path.join(out_dir, f"{key}.jpg")
    if os.path.exists(out_path) and not force:
        print(f"  [skip] {key} - already exists")
        return True

    print(f"  [fetch] {key} -> '{title}'", end=" ... ", flush=True)
    url = fetch_wikipedia_thumbnail(title, size)
    if not url:
        print("no image found")
        return False
    ok = download_and_save(url, out_path, size)
    print("saved" if ok else "failed")
    time.sleep(REQUEST_SLEEP)
    return ok


def download_all(targets, out_dir, force=False, size=IMAGE_SIZE):
    """targets: iterable of (key, wikipedia_title). Returns (ok, failed)."""
    targets = list(targets)
    print(f"Downloading {len(targets)} images -> {out_dir}\n")
    ok = failed = 0
    for i, (key, title) in enumerate(targets, 1):
        print(f"[{i}/{len(targets)}] {key}")
        if download_one(key, title, out_dir, force=force, size=size):
            ok += 1
        else:
            failed += 1
    print(f"\nDone: {ok} downloaded, {failed} failed.")
    if failed:
        print("Re-run with --force to retry failures.")
    return ok, failed
