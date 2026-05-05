#!/usr/bin/env python3
"""
process_ai.py — Enriches baby food papers in SQLite DBs with AI-generated metadata
using a local Ollama LLM (default: mistral).

Fills in:
  - AI_primary_field: one of the 7 baby food research categories
  - AI_summary: 2-3 sentence plain-language summary
  - recommendation_summary: actionable recommendation for parents
  - evidence_strength: strong | moderate | limited | mixed
  - likelihood_score: 0–100, probability the finding is real
  - seriousness_score: 0–10, importance/severity of the outcome
  - participant_count: extracted from abstract if available

Usage:
    python process_ai.py --db ../data/papers_peanut_allergy.db
    python process_ai.py --all
    python process_ai.py --all --model llama3 --batch-size 5
"""

import argparse
import glob
import json
import os
import re
import sqlite3
import time

from openai import OpenAI

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, '..', 'data'))

OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://localhost:11434/v1")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "mistral")

PRIMARY_FIELDS = [
    "Allergen Introduction",
    "Feeding Milestones",
    "Nutrients & Supplements",
    "Food Safety",
    "Gut Health",
    "Growth & Development",
    "Breastfeeding & Formula",
]

SYSTEM_PROMPT = """You are a pediatric nutrition research assistant helping parents understand scientific evidence.
Respond ONLY with valid JSON. Be concise and accurate. Use plain language parents can understand."""

CLASSIFICATION_PROMPT = """Classify this baby food research paper and extract structured information.

Title: {title}
Abstract: {abstract}

Respond with ONLY this JSON (no markdown, no explanation):
{{
  "AI_primary_field": "<one of: Allergen Introduction | Feeding Milestones | Nutrients & Supplements | Food Safety | Gut Health | Growth & Development | Breastfeeding & Formula>",
  "AI_summary": "<2-3 sentence plain English summary for parents>",
  "recommendation_summary": "<one sentence: what this means for parents, e.g. 'Introduce peanuts early to reduce allergy risk'>",
  "evidence_strength": "<strong | moderate | limited | mixed>",
  "likelihood_score": <0-100 integer, how likely the finding is real/replicable>,
  "seriousness_score": <0-10 float, importance of this outcome for baby health>,
  "participant_count": <integer or null if not mentioned>
}}

Guidelines:
- evidence_strength: strong = large RCT or meta-analysis; moderate = smaller RCT or prospective cohort; limited = case-control, cross-sectional, or small study; mixed = conflicting results
- likelihood_score: 90+ for meta-analyses, 70-89 for well-powered RCTs, 50-69 for observational, 30-49 for small/preliminary
- seriousness_score: 9-10 = life-threatening (anaphylaxis, severe malnutrition); 7-8 = significant health impact; 5-6 = moderate concern; 3-4 = minor concern; 1-2 = minimal impact"""


def get_client(base_url=OLLAMA_BASE, model=DEFAULT_MODEL):
    return OpenAI(base_url=base_url, api_key="ollama"), model


def call_llm(client, model, prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=400,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt
                print(f"  [retry] LLM error ({e}), waiting {wait}s...")
                time.sleep(wait)
            else:
                raise


def parse_json_response(text):
    # Strip markdown code fences if present
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try extracting first JSON object
        m = re.search(r'\{.*\}', text, re.DOTALL)
        if m:
            return json.loads(m.group())
        raise


def process_paper(client, model, paper_id, title, abstract):
    if not title:
        return None
    if not abstract:
        abstract = "(no abstract available)"

    prompt = CLASSIFICATION_PROMPT.format(
        title=title[:500],
        abstract=abstract[:1500],
    )
    raw = call_llm(client, model, prompt)
    data = parse_json_response(raw)

    # Validate and clamp
    field = data.get("AI_primary_field", "")
    if field not in PRIMARY_FIELDS:
        field = PRIMARY_FIELDS[0]

    likelihood = data.get("likelihood_score")
    if isinstance(likelihood, (int, float)):
        likelihood = max(0, min(100, int(likelihood)))
    else:
        likelihood = None

    seriousness = data.get("seriousness_score")
    if isinstance(seriousness, (int, float)):
        seriousness = max(0.0, min(10.0, float(seriousness)))
    else:
        seriousness = None

    evidence = data.get("evidence_strength", "limited")
    if evidence not in ("strong", "moderate", "limited", "mixed"):
        evidence = "limited"

    participant_count = data.get("participant_count")
    if participant_count is not None:
        try:
            participant_count = int(participant_count)
        except (ValueError, TypeError):
            participant_count = None

    return {
        "AI_primary_field": field,
        "AI_summary": data.get("AI_summary", ""),
        "recommendation_summary": data.get("recommendation_summary", ""),
        "evidence_strength": evidence,
        "likelihood_score": likelihood,
        "seriousness_score": seriousness,
        "participant_count": participant_count,
    }


def process_db(db_path, client, model, batch_size=10, force=False):
    print(f"\n[process] DB: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    if force:
        rows = conn.execute("SELECT paperId, title, abstract FROM papers").fetchall()
    else:
        rows = conn.execute(
            "SELECT paperId, title, abstract FROM papers WHERE AI_primary_field IS NULL OR AI_primary_field = ''"
        ).fetchall()

    total = len(rows)
    print(f"[process] Papers to process: {total}")
    if total == 0:
        conn.close()
        return

    success, failed = 0, 0
    for i, row in enumerate(rows, 1):
        paper_id = row["paperId"]
        print(f"  [{i}/{total}] {paper_id[:20]}... {row['title'][:60] if row['title'] else '(no title)'}")
        try:
            result = process_paper(client, model, paper_id, row["title"], row["abstract"])
            if result:
                conn.execute("""
                    UPDATE papers SET
                        AI_primary_field = ?,
                        AI_summary = ?,
                        recommendation_summary = ?,
                        evidence_strength = ?,
                        likelihood_score = ?,
                        seriousness_score = ?,
                        participant_count = ?
                    WHERE paperId = ?
                """, (
                    result["AI_primary_field"],
                    result["AI_summary"],
                    result["recommendation_summary"],
                    result["evidence_strength"],
                    result["likelihood_score"],
                    result["seriousness_score"],
                    result["participant_count"],
                    paper_id,
                ))
                if i % batch_size == 0:
                    conn.commit()
                success += 1
        except Exception as e:
            print(f"  [error] {paper_id}: {e}")
            failed += 1
            continue

    conn.commit()
    conn.close()
    print(f"[process] Done. Success: {success}, Failed: {failed}")


def main():
    parser = argparse.ArgumentParser(description="Enrich baby food papers with AI metadata")
    parser.add_argument("--db", help="Path to a specific SQLite DB file")
    parser.add_argument("--all", action="store_true", help="Process all DBs in data directory")
    parser.add_argument("--model", default=DEFAULT_MODEL, help=f"Ollama model (default: {DEFAULT_MODEL})")
    parser.add_argument("--base-url", default=OLLAMA_BASE, help=f"Ollama base URL (default: {OLLAMA_BASE})")
    parser.add_argument("--batch-size", type=int, default=10, help="Commit every N records")
    parser.add_argument("--force", action="store_true", help="Re-process already-classified papers")
    args = parser.parse_args()

    client, model = get_client(base_url=args.base_url, model=args.model)
    print(f"[process] Using model: {model} at {args.base_url}")

    # Test connection
    try:
        test = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Say OK"}],
            max_tokens=5,
        )
        print(f"[process] LLM connection OK: {test.choices[0].message.content.strip()}")
    except Exception as e:
        print(f"[error] Cannot connect to Ollama at {args.base_url}: {e}")
        print("Make sure Ollama is running: ollama serve")
        return

    if args.all:
        dbs = sorted(glob.glob(os.path.join(DATA_DIR, 'papers_*.db')))
        if not dbs:
            print(f"[error] No databases found in {DATA_DIR}")
            return
        for db_path in dbs:
            process_db(db_path, client, model, batch_size=args.batch_size, force=args.force)
    elif args.db:
        process_db(args.db, client, model, batch_size=args.batch_size, force=args.force)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
