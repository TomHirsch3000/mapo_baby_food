#!/usr/bin/env python3
"""
download_topic_images.py — Wikipedia thumbnails for each topic, used as the
visual anchor inside the hexagons on the landing page.

Output: frontend/public/images/topics/<topic_key>.jpg

Usage:
    python backend/download_topic_images.py
    python backend/download_topic_images.py --force
"""

import argparse
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import console
import images
from claims import TOPICS

console.init()

OUT_DIR = os.path.normpath(
    os.path.join(SCRIPT_DIR, "..", "frontend", "public", "images", "topics")
)

# Picked for a recognisable lead image rather than topical precision - these are
# visual cues, not citations. Several obvious articles ("Language acquisition",
# "Co-sleeping", "Read-aloud") have no lead image at all.
TOPIC_ARTICLES = {
    "food":     "Baby food",
    "sleep":    "Infant bed",
    "screens":  "Screen time",
    "activity": "Tummy time",
    "learning": "Picture book",
}


def main():
    parser = argparse.ArgumentParser(description="Download topic images from Wikipedia")
    parser.add_argument("--force", action="store_true", help="re-download existing")
    parser.add_argument("--topic", help="single topic key")
    args = parser.parse_args()

    missing = [t for t in TOPICS if t not in TOPIC_ARTICLES]
    if missing:
        print(f"[warn] no Wikipedia article mapped for: {', '.join(missing)}")

    if args.topic:
        if args.topic not in TOPIC_ARTICLES:
            print(f"[error] unknown topic: {args.topic}")
            raise SystemExit(1)
        targets = [(args.topic, TOPIC_ARTICLES[args.topic])]
    else:
        targets = [(k, v) for k, v in TOPIC_ARTICLES.items() if k in TOPICS]

    images.download_all(targets, OUT_DIR, force=args.force)


if __name__ == "__main__":
    main()
