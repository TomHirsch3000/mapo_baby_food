#!/usr/bin/env python3
"""
snapshot_db.py — Take a safe, single-file copy of claims.db for transfer.

Do NOT just copy data/claims.db. It runs in WAL mode, so recent commits live in
the -wal sidecar until a checkpoint folds them back in. Copying the .db alone
while an evaluation run is in progress silently loses whatever is still in the
WAL, and copying the three files separately can produce an inconsistent set.

VACUUM INTO takes a transactionally consistent snapshot of a live database into
one new file, and compacts it on the way out. It is safe to run mid-evaluation.

Usage:
    python backend/snapshot_db.py                        # -> data/claims-snapshot.db
    python backend/snapshot_db.py --out ~/Desktop/x.db
    python backend/snapshot_db.py --serve                # offer it over the LAN
"""

import argparse
import os
import socket
import sqlite3
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

import console

console.init()

DATA_DIR = os.path.normpath(os.path.join(SCRIPT_DIR, "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "claims.db")
DEFAULT_OUT = os.path.join(DATA_DIR, "claims-snapshot.db")


def local_ip():
    """The address another machine on the same wifi can actually reach."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))     # no packets sent; just picks the route
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def snapshot(db_path, out_path):
    if os.path.exists(out_path):
        os.remove(out_path)           # VACUUM INTO refuses to overwrite

    conn = sqlite3.connect(db_path, timeout=60)
    conn.execute("PRAGMA busy_timeout=60000")
    # Escaping: the path is ours, but a stray quote would still break the SQL.
    conn.execute(f"VACUUM INTO '{out_path.replace(chr(39), chr(39) * 2)}'")

    counts = {
        "papers": conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0],
        "links": conn.execute("SELECT COUNT(*) FROM claim_papers").fetchone()[0],
        "judged": conn.execute(
            "SELECT COUNT(*) FROM claim_papers WHERE stance IS NOT NULL AND stance != ''"
        ).fetchone()[0],
        "with_reasoning": conn.execute(
            "SELECT COUNT(*) FROM claim_papers WHERE direction IS NOT NULL AND direction != ''"
        ).fetchone()[0],
    }
    conn.close()

    size = os.path.getsize(out_path) / (1024 * 1024)
    print(f"Snapshot written: {out_path}  ({size:.1f} MB)")
    print(f"  {counts['papers']} papers, {counts['links']} claim-paper links")
    print(f"  {counts['judged']} judged, {counts['with_reasoning']} carrying reasoning")
    return out_path


def serve(path, port=8000):
    """Hand the file to another machine on the same wifi. No accounts, no cloud."""
    import http.server
    import socketserver

    directory = os.path.dirname(os.path.abspath(path))
    name = os.path.basename(path)

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=directory, **kw)

        def log_message(self, fmt, *args):
            print(f"  [{self.address_string()}] {fmt % args}")

    print(f"\nServing {directory} on port {port}.")
    print(f"On the other machine, open or download:\n")
    print(f"    http://{local_ip()}:{port}/{name}\n")
    print("Ctrl-C when the transfer finishes.")
    with socketserver.TCPServer(("", port), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


def main():
    parser = argparse.ArgumentParser(description="Safe snapshot of claims.db")
    parser.add_argument("--db", default=DB_PATH)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--serve", action="store_true",
                        help="serve the snapshot over the local network")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if not os.path.exists(args.db):
        print(f"[error] {args.db} not found")
        raise SystemExit(1)

    out = snapshot(args.db, args.out)
    if args.serve:
        serve(out, args.port)


if __name__ == "__main__":
    main()
