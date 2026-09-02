#!/usr/bin/env python3
"""
export_verdicts.py — Move verdicts between machines through git, one file per shard.

This exists alongside `snapshot_db.py`, and the two are not competing. The
snapshot is the whole corpus in one file: abstracts, citations, verdicts, the
lot. It is how a machine gets bootstrapped, and it deltas well in git because
VACUUM INTO lays pages out deterministically. What it cannot do is let two
machines write at once. It is a single binary blob under a single path, so when
both halves of a sharded pass try to commit one, git has nothing to offer but
"take mine or take theirs" — and either answer silently discards a shard.

This writes the verdicts as text instead, partitioned the same way the work is:
one CSV per file in shards/. Each machine touches only its own, so concurrent
commits from both halves merge with no conflict at all, rather than merely
usually. Text also means a verdict change is readable in a diff and `git log -p`
answers "when did this claim flip, and to what".

Partitioning matters more than it looks. A single CSV sorted by claim_key does
NOT merge cleanly, because the shards interleave alphabetically - baby_led_weaning
(mac), back_to_sleep (windows), background_tv (windows), bilingual_no_delay (mac)
- so edits from the two machines land inside each other's diff hunks. Splitting
by shard is what makes the disjointness the pass already has visible to git.

Authority: `data/claims.db` is what a run reads and writes. These CSVs are its
outbound half - regenerate after a run, commit, and the other machine imports.
An import only ever touches the verdict columns of rows it names; papers,
citations and any claim outside the file are left exactly as they were.

Round-trip is lossless but for one forced normalisation: CSV cannot tell an
empty string from a NULL, so a column holding "" comes back NULL. Verified by
wiping a shard from a copy and restoring it - 7,767 of 7,769 rows identical, the
two exceptions both an empty stance_summary. NULLs themselves survive intact.

Usage:
    python backend/export_verdicts.py                    # all shards -> data/verdicts/
    python backend/export_verdicts.py --shard mac
    python backend/export_verdicts.py --import data/verdicts/windows.csv
    python backend/export_verdicts.py --import data/verdicts/windows.csv --dry-run
"""

import argparse
import csv
import glob
import os
import sqlite3
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, ".."))
DB_PATH = os.path.join(ROOT, "data", "claims.db")
OUT_DIR = os.path.join(ROOT, "data", "verdicts")
SHARD_DIR = os.path.join(ROOT, "shards")

# The two key columns, then everything a pass writes. Deliberately NOT
# `SELECT *`: a later migration that adds a column would otherwise change the
# file's shape silently, and every row would show as modified in the diff.
KEYS = ["claim_key", "paperId"]
VERDICT_COLS = [
    "stance", "confidence", "stance_summary", "evidence_strength", "study_type",
    "finding", "direction", "evaluated_at", "evaluated_by", "prompt_version",
    "claim_text_used",
]
COLUMNS = KEYS + VERDICT_COLS


def shard_claims(path):
    """Claim keys from a shards/*.txt file — every line that is not a comment."""
    with open(path, encoding="utf-8") as fh:
        return " ".join(l for l in fh if not l.startswith("#")).split()


def export(conn, name, keys):
    """Write one shard's verdicts, ordered so the file is stable between runs.

    Row order has to be deterministic or every export produces a diff against
    itself. Ordering by the primary key does that, and has the side effect of
    grouping a claim's papers together where a reader expects them.
    """
    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"{name}.csv")
    ph = ",".join("?" * len(keys))
    rows = conn.execute(
        f"SELECT {','.join(COLUMNS)} FROM claim_papers "
        f"WHERE claim_key IN ({ph}) ORDER BY claim_key, paperId", keys).fetchall()

    # newline="" per the csv docs, and \n rather than the platform default:
    # these files are written on both a Mac and a Windows laptop, and a line
    # ending that follows the machine would show every row as changed.
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(COLUMNS)
        w.writerows(rows)

    judged = sum(1 for r in rows if r[COLUMNS.index("evaluated_by")])
    print(f"  {os.path.relpath(out, ROOT):<34} {len(rows):>5,} rows  "
          f"{judged:>5,} judged  {os.path.getsize(out)/1048576:.2f} MB")
    return len(rows)


def import_csv(conn, path, dry_run=False):
    """Apply a CSV's verdicts onto the local database.

    Rows are matched on (claim_key, paperId) and only the verdict columns are
    written, so importing the other machine's half cannot disturb this one's.
    A pair in the file that does not exist locally is counted and skipped rather
    than inserted: it means the two corpora have diverged, which is worth being
    told about and is not something this script should paper over by inventing a
    row with no paper behind it.
    """
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = set(COLUMNS) - set(reader.fieldnames or [])
        if missing:
            sys.exit(f"[error] {path} is missing columns: {sorted(missing)}")
        rows = list(reader)

    applied = skipped = unjudged = 0
    for r in rows:
        # Test on the stance, not on evaluated_by. The Aug-26 mistral pass ran
        # before the provenance columns existed, so its verdicts carry a stance
        # and no model tag; keying off evaluated_by drops every one of them and
        # makes a restore quietly lossy - 2,703 rows on this database. A row with
        # neither is genuinely unevaluated and there is nothing to carry.
        if not r["stance"] and not r["evaluated_by"]:
            unjudged += 1
            continue
        cur = conn.execute(
            "SELECT 1 FROM claim_papers WHERE claim_key = ? AND paperId = ?",
            (r["claim_key"], r["paperId"]))
        if not cur.fetchone():
            skipped += 1
            continue
        if not dry_run:
            conn.execute(
                f"UPDATE claim_papers SET {','.join(c + ' = ?' for c in VERDICT_COLS)} "
                f"WHERE claim_key = ? AND paperId = ?",
                [r[c] or None for c in VERDICT_COLS] + [r["claim_key"], r["paperId"]])
        applied += 1

    if not dry_run:
        conn.commit()
    print(f"{'[dry-run] ' if dry_run else ''}{applied:,} verdicts applied from "
          f"{os.path.relpath(path, ROOT)}")
    if unjudged:
        print(f"  {unjudged:,} rows carried no verdict upstream — left alone")
    if skipped:
        print(f"  ** {skipped:,} pairs are not in this database — the corpora "
              f"have diverged **")
    return applied


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    p.add_argument("--db", default=DB_PATH)
    p.add_argument("--shard", help="export just this shard (default: all)")
    p.add_argument("--import", dest="import_path", help="apply a CSV to the database")
    p.add_argument("--dry-run", action="store_true", help="with --import, change nothing")
    args = p.parse_args()

    if not os.path.exists(args.db):
        sys.exit(f"[error] no database at {args.db}")
    conn = sqlite3.connect(args.db)

    if args.import_path:
        import_csv(conn, args.import_path, args.dry_run)
        conn.close()
        return

    paths = sorted(glob.glob(os.path.join(SHARD_DIR, "*.txt")))
    if args.shard:
        paths = [q for q in paths if os.path.basename(q)[:-4] == args.shard]
        if not paths:
            sys.exit(f"[error] no shard named {args.shard} in shards/")

    print(f"Exporting verdicts from {os.path.relpath(args.db, ROOT)}:")
    seen, total = {}, 0
    for path in paths:
        name = os.path.basename(path)[:-4]
        keys = shard_claims(path)
        # The shards are meant to be disjoint, and every guarantee here rests on
        # that. Cheap to check, and a silent overlap would mean two machines
        # writing one claim and each overwriting the other on import.
        for k in keys:
            if k in seen:
                print(f"  ** {k} is in both {seen[k]} and {name} — shards overlap **")
            seen[k] = name
        total += export(conn, name, keys)

    # Pairs belonging to no shard. Usually benign - a claim dropped from the
    # registry keeps its papers in the database on purpose (gold/dropped_claims.md),
    # so its rows outlive it. A pair whose claim IS still in the registry is the
    # case worth shouting about: it is live, and no machine has been given it.
    covered = conn.execute("SELECT COUNT(*) FROM claim_papers").fetchone()[0]
    if total != covered:
        from claims import CLAIMS
        orphans = [k for (k,) in conn.execute("SELECT DISTINCT claim_key FROM claim_papers")
                   if k not in seen]
        retired = sorted(k for k in orphans if k not in CLAIMS)
        live = sorted(k for k in orphans if k in CLAIMS)
        print(f"  note: {covered - total:,} of {covered:,} pairs are in no shard")
        if retired:
            print(f"        {len(retired)} dropped from the registry, papers kept "
                  f"deliberately: {', '.join(retired)}")
        if live:
            print(f"  ** {len(live)} claim(s) are LIVE but in no shard — nothing "
                  f"will re-evaluate them: {', '.join(live)} **")
    conn.close()


if __name__ == "__main__":
    main()
