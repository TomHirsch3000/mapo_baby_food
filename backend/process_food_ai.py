#!/usr/bin/env python3
"""
process_food_ai.py — Enriches food_papers_*.db databases with AI-generated
recommendation summaries using a local Ollama LLM (default: mistral).

For each paper (title + abstract), generates a concise recommendation summary
that captures what the paper says about this food for infants/children.
Results are stored back in the food database and can be used to cluster papers.

Usage:
    python process_food_ai.py --db ../data/food_papers_broccoli.db
    python process_food_ai.py --all                         # process all food DBs
    python process_food_ai.py --all --model llama3
    python process_food_ai.py --all --batch-size 5 --force  # re-process existing
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

SYSTEM_PROMPT = (
    "You are a pediatric nutrition research assistant. "
    "Respond ONLY with valid JSON. Be concise. Use plain language parents can understand."
)

SUMMARY_PROMPT = """\
Read this infant/child nutrition research paper and produce a structured summary.

Title: {title}
Abstract: {abstract}

Respond with ONLY this JSON (no markdown, no explanation):
{{
  "recommendation_summary": "<one sentence: the key finding for parents, e.g. 'Introducing broccoli before 12 months may support gut microbiome diversity'>",
  "evidence_strength": "<strong | moderate | limited | mixed>",
  "likelihood_score": <0-100 integer, how likely the finding replicates>,
  "seriousness_score": <0.0-10.0 float, health importance for the baby>
}}

Guidelines:
- recommendation_summary: focus on what parents should know; mention the food and the outcome.
- evidence_strength: strong = large RCT/meta-analysis; moderate = smaller RCT/prospective cohort; limited = small/cross-sectional; mixed = conflicting results.
- likelihood_score: 90+ for meta-analyses, 70-89 for well-powered RCTs, 50-69 for observational, 30-49 for preliminary.
- seriousness_score: 9-10 = life-threatening; 7-8 = significant impact; 5-6 = moderate; 3-4 = minor; 1-2 = minimal."""


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
                max_tokens=300,
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
    text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
    return None


def validate_result(data):
    if not isinstance(data, dict):
        return None
    summary = data.get("recommendation_summary", "")
    if not summary or not isinstance(summary, str):
        return None
    strength = data.get("evidence_strength", "limited")
    if strength not in ("strong", "moderate", "limited", "mixed"):
        strength = "limited"
    try:
        likelihood = max(0, min(100, int(data.get("likelihood_score", 50))))
    except (TypeError, ValueError):
        likelihood = 50
    try:
        seriousness = max(0.0, min(10.0, float(data.get("seriousness_score", 5.0))))
    except (TypeError, ValueError):
        seriousness = 5.0
    return {
        "recommendation_summary": summary[:500],
        "evidence_strength": strength,
        "likelihood_score": likelihood,
        "seriousness_score": seriousness,
    }


def ensure_columns(conn):
    existing = {row[1] for row in conn.execute("PRAGMA table_info(papers)").fetchall()}
    for col, typedef in [
        ("recommendation_summary", "TEXT"),
        ("evidence_strength",      "TEXT"),
        ("likelihood_score",       "INTEGER"),
        ("seriousness_score",      "REAL"),
    ]:
        if col not in existing:
            conn.execute(f"ALTER TABLE papers ADD COLUMN {col} {typedef}")
    conn.commit()


def process_db(db_path, client, model, batch_size=10, force=False):
    food_key = os.path.basename(db_path).replace("food_papers_", "").replace(".db", "")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    ensure_columns(conn)

    if force:
        rows = conn.execute(
            "SELECT paperId, title, abstract FROM papers WHERE abstract != '' AND abstract IS NOT NULL"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT paperId, title, abstract FROM papers "
            "WHERE recommendation_summary IS NULL AND abstract != '' AND abstract IS NOT NULL"
        ).fetchall()

    total = len(rows)
    if total == 0:
        print(f"  [{food_key}] nothing to process")
        conn.close()
        return 0

    print(f"  [{food_key}] processing {total} papers...")
    done = 0
    for i, row in enumerate(rows):
        prompt = SUMMARY_PROMPT.format(
            title=row["title"] or "(no title)",
            abstract=(row["abstract"] or "")[:1500],
        )
        try:
            raw = call_llm(client, model, prompt)
            data = parse_json_response(raw)
            result = validate_result(data) if data else None
        except Exception as e:
            print(f"    [error] paper {row['paperId']}: {e}")
            result = None

        if result:
            conn.execute(
                """UPDATE papers SET
                    recommendation_summary = ?,
                    evidence_strength      = ?,
                    likelihood_score       = ?,
                    seriousness_score      = ?
                WHERE paperId = ?""",
                (
                    result["recommendation_summary"],
                    result["evidence_strength"],
                    result["likelihood_score"],
                    result["seriousness_score"],
                    row["paperId"],
                ),
            )
            done += 1
        else:
            print(f"    [skip] could not parse response for {row['paperId']}")

        if (i + 1) % batch_size == 0:
            conn.commit()
            print(f"    ... {i + 1}/{total} done")

    conn.commit()
    conn.close()
    print(f"  [{food_key}] done: {done}/{total} papers enriched")
    return done


def cluster_summaries(db_path, n_clusters=None):
    """
    Cluster recommendation summaries using TF-IDF + KMeans and store cluster labels.
    Run after process_db to group similar recommendations.
    """
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.cluster import KMeans
        import numpy as np
    except ImportError:
        print("  [skip] clustering requires scikit-learn: pip install scikit-learn")
        return

    food_key = os.path.basename(db_path).replace("food_papers_", "").replace(".db", "")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Ensure recommendation_cluster column exists
    existing = {row[1] for row in conn.execute("PRAGMA table_info(papers)").fetchall()}
    if "recommendation_cluster" not in existing:
        conn.execute("ALTER TABLE papers ADD COLUMN recommendation_cluster INTEGER")
        conn.commit()

    rows = conn.execute(
        "SELECT paperId, recommendation_summary FROM papers WHERE recommendation_summary IS NOT NULL"
    ).fetchall()

    if len(rows) < 3:
        print(f"  [{food_key}] too few summaries to cluster ({len(rows)})")
        conn.close()
        return

    texts = [r["recommendation_summary"] for r in rows]
    ids = [r["paperId"] for r in rows]

    k = n_clusters or max(2, min(8, len(texts) // 5))
    vectorizer = TfidfVectorizer(stop_words="english", max_features=500)
    X = vectorizer.fit_transform(texts)

    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(X)

    for paper_id, label in zip(ids, labels):
        conn.execute(
            "UPDATE papers SET recommendation_cluster = ? WHERE paperId = ?",
            (int(label), paper_id),
        )
    conn.commit()

    # Print cluster summaries
    clusters = {}
    for paper_id, label, text in zip(ids, labels, texts):
        clusters.setdefault(int(label), []).append(text)
    print(f"  [{food_key}] {k} clusters:")
    for cid, items in sorted(clusters.items()):
        print(f"    Cluster {cid} ({len(items)} papers): {items[0][:100]}...")

    conn.close()


def main():
    parser = argparse.ArgumentParser(description="Enrich food paper DBs with AI recommendation summaries")
    parser.add_argument("--db", help="Path to a single food_papers_*.db")
    parser.add_argument("--all", action="store_true", help="Process all food_papers_*.db in DATA_DIR")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--force", action="store_true", help="Re-process papers that already have summaries")
    parser.add_argument("--cluster", action="store_true", help="Also run clustering after enrichment")
    parser.add_argument("--cluster-only", action="store_true", help="Skip LLM, only run clustering")
    args = parser.parse_args()

    if not args.db and not args.all:
        parser.error("Provide --db <path> or --all")

    if args.all:
        dbs = sorted(glob.glob(os.path.join(DATA_DIR, "food_papers_*.db")))
    else:
        dbs = [args.db]

    if not dbs:
        print(f"No food databases found in {DATA_DIR}")
        return

    print(f"Model: {args.model}  |  DBs: {len(dbs)}  |  Batch: {args.batch_size}")

    if not args.cluster_only:
        client, model = get_client(model=args.model)
        # Test connection
        try:
            client.models.list()
        except Exception as e:
            print(f"[error] Cannot reach Ollama at {OLLAMA_BASE}: {e}")
            print("Make sure Ollama is running:  ollama serve")
            return

        total_done = 0
        for db_path in dbs:
            total_done += process_db(db_path, client, model, args.batch_size, args.force)
        print(f"\nTotal: {total_done} papers enriched across {len(dbs)} databases")

    if args.cluster or args.cluster_only:
        print("\nClustering summaries...")
        for db_path in dbs:
            cluster_summaries(db_path)


if __name__ == "__main__":
    main()
