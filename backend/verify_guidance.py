#!/usr/bin/env python3
"""
verify_guidance.py — Re-fetch every guidance page and prove the quote is on it.

The sourcing agents were told to copy verbatim. One of them reported that the
fetch summariser had handed it a sentence that was not on the page at all
("Your baby does not need sugar.") and dropped it. That is a fluent, plausible,
entirely invented quote about infant feeding — the exact failure the evaluator's
own quote-checking exists to catch, arriving through a different door.

Guidance is shown to parents as official advice. A misattributed sentence about
SIDS or allergen introduction is a safety problem, not a formatting error. So
nothing is trusted because an agent said it fetched it: every quote is checked
against the live page, and anything that does not verify is reported rather than
quietly kept.

    python backend/verify_guidance.py --scratch <dir>
    python backend/verify_guidance.py --scratch <dir> --write-clean
"""

import argparse
import glob
import html
import json
import os
import re
import sys

import requests

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import console

console.init()

# Some of these hosts refuse a bare python-requests UA (beststartinlife.gov.uk
# and publications.aap.org both 403), so we identify as a browser.
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

TAGS = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.S | re.I)
ANGLE = re.compile(r"<[^>]+>")


def normalise(text):
    """Lowercase, unify the punctuation publishers vary on, collapse space.

    Same treatment the evaluator gives an abstract quote: a curly apostrophe or
    a line break is not a real difference, and failing a quote on one would hide
    the failures that matter.
    """
    text = html.unescape(text or "")
    for a, b in [("’", "'"), ("‘", "'"), ("“", '"'),
                 ("”", '"'), ("–", "-"), ("—", "-"),
                 ("‐", "-"), (" ", " ")]:
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", text.lower()).strip()


def words(text):
    """The alphanumeric word stream, punctuation discarded entirely.

    Stripping tags leaves a space where the markup was, so a page carrying
    "fish,</em> beyond" reads back as "fish , beyond" and an exact substring
    test fails against a quote that is genuinely on the page. Six of the first
    seven failures here were exactly that, not fabrication — which would have
    meant discarding real guidance. Comparing word streams ignores the
    difference. "&" is spelled out first because publishers render it both ways.
    """
    return " ".join(re.findall(r"[a-z0-9]+",
                               normalise(text).replace("&", " and ")))


def page_text(url, cache):
    if url in cache:
        return cache[url]
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
        body = "" if r.status_code >= 400 else words(
            ANGLE.sub(" ", TAGS.sub(" ", r.text)))
        cache[url] = (r.status_code, body)
    except Exception as e:
        cache[url] = (None, "")
        print(f"    [fetch failed] {url} — {e}")
    return cache[url]


def main():
    p = argparse.ArgumentParser(description="Prove every guidance quote is real")
    p.add_argument("--scratch", required=True)
    p.add_argument("--write-clean", action="store_true",
                   help="write guidance_verified.json with failures stripped")
    args = p.parse_args()

    rows = []
    for path in sorted(glob.glob(os.path.join(args.scratch, "guidance_*_out.json"))):
        rows += json.load(open(path, encoding="utf-8"))
    print(f"{len(rows)} claims from {len(glob.glob(os.path.join(args.scratch, 'guidance_*_out.json')))} files\n")

    cache = {}
    ok = bad = skipped = 0
    failures = []
    for row in rows:
        for body in ("nhs", "aap"):
            b = row.get(body) or {}
            if not b.get("found"):
                skipped += 1
                continue
            quote, url = b.get("quote", ""), b.get("url", "")
            if not quote or not url:
                b["verified"] = False
                failures.append((row["claim_key"], body, "no quote or url", url))
                bad += 1
                continue
            status, text = page_text(url, cache)
            hit = bool(words(quote)) and words(quote) in text
            b["verified"] = bool(hit)
            if hit:
                ok += 1
            else:
                bad += 1
                why = f"HTTP {status}" if not text else "quote not on page"
                failures.append((row["claim_key"], body, why, url))

    print(f"  verified   {ok}")
    print(f"  FAILED     {bad}")
    print(f"  not found (nothing to check)  {skipped}\n")
    for key, body, why, url in failures:
        print(f"  [{why:<18}] {key:<26} {body}  {url[:66]}")

    if args.write_clean:
        # A quote that cannot be proven is dropped, not downgraded. There is no
        # safe way to show a parent a sentence we cannot find on the page.
        for row in rows:
            for body in ("nhs", "aap"):
                b = row.get(body) or {}
                if b.get("found") and not b.get("verified"):
                    b.update(found=False, quote="", paraphrase="", url="",
                             dropped_reason="quote could not be verified")
        out = os.path.join(args.scratch, "guidance_verified.json")
        json.dump(rows, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
