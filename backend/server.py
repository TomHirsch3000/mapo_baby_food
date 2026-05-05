#!/usr/bin/env python3
"""
server.py — Flask API for the baby food research map frontend.
Serves paper detail networks and full-text search across SQLite databases.
"""

import glob
import os
import sqlite3
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _find_db_dir():
    env_dir = os.environ.get('MAPO_DB_DIR')
    if env_dir and glob.glob(os.path.join(env_dir, 'papers_*.db')):
        return env_dir
    if glob.glob(os.path.join(SCRIPT_DIR, '..', 'data', 'papers_*.db')):
        return os.path.normpath(os.path.join(SCRIPT_DIR, '..', 'data'))
    if glob.glob(os.path.join(SCRIPT_DIR, 'papers_*.db')):
        return SCRIPT_DIR
    # Walk up
    candidate = SCRIPT_DIR
    for _ in range(6):
        candidate = os.path.dirname(candidate)
        for subdir in ['data', '.']:
            target = os.path.join(candidate, subdir)
            if glob.glob(os.path.join(target, 'papers_*.db')):
                return target
    return os.path.normpath(os.path.join(SCRIPT_DIR, '..', 'data'))


DB_DIR = _find_db_dir()


def get_all_db_paths():
    return sorted(glob.glob(os.path.join(DB_DIR, 'papers_*.db')))


def topic_from_db_path(db_path):
    name = os.path.basename(db_path).replace('papers_', '').replace('.db', '')
    if name.endswith('_all'):
        name = name[:-4]
    return name.replace('_', ' ').title()


def open_conn(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def column_names(conn):
    return {r[1] for r in conn.execute("PRAGMA table_info(papers)").fetchall()}


def _safe(row, col, default=""):
    return row[col] if col in row.keys() else default


def format_node(row, node_type=None):
    yr = row['year'] if 'year' in row.keys() else None
    pub_date = _safe(row, 'publicationDate') or _safe(row, 'publication_date')
    if not yr and pub_date:
        try:
            yr = int(str(pub_date).split('-')[0])
        except Exception:
            yr = 2000

    cite_count = _safe(row, 'cited_by_count', 0) or _safe(row, 'citationCount', 0) or 0

    node = {
        "id": row['paperId'],
        "title": _safe(row, 'title'),
        "year": yr,
        "citationCount": cite_count,
        "primaryField": _safe(row, 'AI_primary_field') or _safe(row, 'primary_concept') or "Unassigned",
        "abstract": _safe(row, 'AI_summary') or _safe(row, 'abstract') or "No abstract available.",
        "authors": _safe(row, 'all_author_names') or _safe(row, 'first_author_name') or "Unknown",
        "institutions": _safe(row, 'all_institution_names') or "",
        "paperNature": _safe(row, 'paper_nature') or None,
        # Baby food specific
        "foodType": _safe(row, 'food_type') or None,
        "ageGroup": _safe(row, 'age_group') or None,
        "recommendationSummary": _safe(row, 'recommendation_summary') or _safe(row, 'AI_recommendation') or None,
        "evidenceStrength": _safe(row, 'evidence_strength') or None,
        "likelihoodScore": row['likelihood_score'] if 'likelihood_score' in row.keys() else None,
        "seriousnessScore": row['seriousness_score'] if 'seriousness_score' in row.keys() else None,
        "participantCount": row['participant_count'] if 'participant_count' in row.keys() else None,
        "studyType": _safe(row, 'study_type') or _safe(row, 'paper_nature') or None,
        "data": dict(row),
    }
    if node_type:
        node["nodeType"] = node_type
    return node


@app.route('/api/paper/<string:paper_id>/details', methods=['GET'])
def get_paper_details(paper_id):
    try:
        min_citations = int(request.args.get('min_citations', 0))
        max_papers = int(request.args.get('max_papers', 200))
    except ValueError:
        return jsonify({"error": "Invalid parameters"}), 400

    for db_path in get_all_db_paths():
        conn = open_conn(db_path)
        try:
            check = conn.execute("SELECT 1 FROM papers WHERE paperId = ?", (paper_id,)).fetchone()
            if not check:
                continue

            raw_edges = conn.execute(
                "SELECT source, target FROM citations WHERE source = ? OR target = ?",
                (paper_id, paper_id)
            ).fetchall()

            connected_ids = {paper_id}
            for row in raw_edges:
                connected_ids.add(row['source'])
                connected_ids.add(row['target'])

            placeholders = ','.join(['?'] * len(connected_ids))
            params = list(connected_ids) + [min_citations, paper_id, max_papers]
            raw_nodes = conn.execute(
                f"SELECT * FROM papers WHERE paperId IN ({placeholders}) "
                f"AND (cited_by_count >= ? OR paperId = ?) LIMIT ?",
                params
            ).fetchall()

            valid_node_ids = {row['paperId'] for row in raw_nodes}
            valid_edges = [
                {"source": row['source'], "target": row['target'], "importance": 1}
                for row in raw_edges
                if row['source'] in valid_node_ids and row['target'] in valid_node_ids
            ]

            return jsonify({
                "nodes": [format_node(row) for row in raw_nodes],
                "edges": valid_edges,
            })
        except Exception as e:
            print(f"[error] DB {db_path}: {e}")
        finally:
            conn.close()

    return jsonify({"error": f"Paper {paper_id} not found in any database."}), 404


@app.route('/api/search', methods=['GET'])
def search_topics():
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({"error": "Query parameter is required"}), 400

    try:
        min_citations = int(request.args.get('min_citations', 0))
        max_papers = int(request.args.get('max_papers', 50))
    except ValueError:
        return jsonify({"error": "Invalid parameters"}), 400

    all_db_paths = get_all_db_paths()
    if not all_db_paths:
        return jsonify({"error": "No databases found. Run the import notebook first."}), 500

    search_term = f'%{query}%'
    all_nodes, all_edges = [], []
    seen_edges, seen_node_ids = set(), set()
    stats = {"core": 0, "foundation": 0, "impact": 0}

    for db_path in all_db_paths:
        conn = open_conn(db_path)
        try:
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            if 'papers' not in tables:
                continue

            cols = column_names(conn)
            search_cols = ['title']
            for opt in ['AI_summary', 'abstract', 'AI_primary_field', 'recommendation_summary', 'food_type']:
                if opt in cols:
                    search_cols.append(opt)
            where_parts = ' OR '.join(f'{c} LIKE ?' for c in search_cols)
            search_params = [search_term] * len(search_cols)
            cite_col = 'cited_by_count' if 'cited_by_count' in cols else 'citationCount'

            core_rows = conn.execute(
                f"SELECT * FROM papers WHERE ({where_parts}) AND {cite_col} >= ? ORDER BY {cite_col} DESC LIMIT ?",
                search_params + [min_citations, max_papers]
            ).fetchall()

            if not core_rows:
                continue

            core_ids = {r['paperId'] for r in core_rows}
            core_id_list = list(core_ids)
            core_ph = ','.join(['?'] * len(core_id_list))

            foundation_edge_rows = conn.execute(
                f"SELECT source, target FROM citations WHERE source IN ({core_ph}) LIMIT 500",
                core_id_list
            ).fetchall()
            foundation_target_ids = {r['target'] for r in foundation_edge_rows} - core_ids

            impact_edge_rows = conn.execute(
                f"SELECT source, target FROM citations WHERE target IN ({core_ph}) LIMIT 500",
                core_id_list
            ).fetchall()
            impact_source_ids = {r['source'] for r in impact_edge_rows} - core_ids

            MAX_CONTEXT = 30

            def fetch_by_ids(id_set, limit):
                if not id_set:
                    return []
                ids = list(id_set)
                ph = ','.join(['?'] * len(ids))
                return conn.execute(
                    f"SELECT * FROM papers WHERE paperId IN ({ph}) ORDER BY {cite_col} DESC LIMIT {limit}",
                    ids
                ).fetchall()

            foundation_rows = fetch_by_ids(foundation_target_ids, MAX_CONTEXT)
            impact_rows = fetch_by_ids(impact_source_ids, MAX_CONTEXT)
            valid_foundation_ids = {r['paperId'] for r in foundation_rows}
            valid_impact_ids = {r['paperId'] for r in impact_rows}
            all_valid_ids = core_ids | valid_foundation_ids | valid_impact_ids

            for row in core_rows:
                if row['paperId'] not in seen_node_ids:
                    all_nodes.append(format_node(row, 'core'))
                    seen_node_ids.add(row['paperId'])
            for row in foundation_rows:
                if row['paperId'] not in seen_node_ids:
                    all_nodes.append(format_node(row, 'foundation'))
                    seen_node_ids.add(row['paperId'])
            for row in impact_rows:
                if row['paperId'] not in seen_node_ids:
                    all_nodes.append(format_node(row, 'impact'))
                    seen_node_ids.add(row['paperId'])

            def add_edge(source, target, edge_type):
                key = f"{source}|{target}"
                if key not in seen_edges and source in all_valid_ids and target in all_valid_ids:
                    seen_edges.add(key)
                    all_edges.append({"source": source, "target": target, "importance": 1, "edgeType": edge_type})

            for r in foundation_edge_rows:
                add_edge(r['source'], r['target'], 'foundation')
            for r in impact_edge_rows:
                add_edge(r['source'], r['target'], 'impact')

            stats["core"] += len(core_rows)
            stats["foundation"] += len(valid_foundation_ids)
            stats["impact"] += len(valid_impact_ids)

        except Exception as e:
            print(f"[error] DB {db_path}: {e}")
        finally:
            conn.close()

    if not all_nodes:
        return jsonify({"nodes": [], "edges": [], "searchQuery": query, "stats": stats})

    return jsonify({"nodes": all_nodes, "edges": all_edges, "searchQuery": query, "stats": stats})


@app.route('/api/status', methods=['GET'])
def status():
    dbs = get_all_db_paths()
    return jsonify({
        "status": "ok",
        "db_dir": DB_DIR,
        "databases": [{"name": topic_from_db_path(p), "path": p} for p in dbs],
        "count": len(dbs)
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print(f"[info] Starting server on port {port}")
    print(f"[info] DB directory: {DB_DIR}")
    dbs = get_all_db_paths()
    if dbs:
        print(f"[info] Databases: {[topic_from_db_path(p) for p in dbs]}")
    else:
        print("[warn] No databases found. Run the import notebook to populate data.")
    app.run(host='0.0.0.0', port=port, debug=True)
