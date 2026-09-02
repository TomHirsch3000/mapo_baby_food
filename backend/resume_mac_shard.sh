#!/bin/sh
# Resume the Mac half of the 2026-09-02 re-evaluation.
#
# Why this is not simply `--stale`: that flag resumes on `direction IS NULL`,
# on the stated assumption that only the current evaluator writes that column.
# Untrue on this database - the Aug-26 mistral pass populated `direction` on
# 2,703 of the Mac shard's 3,784 rows, so `--stale` reads them as already done,
# resumes 1 row instead of 2,704, and exits reporting success with most of the
# shard still judged by the old model. Clearing `direction` on every row this
# pass has not itself written restores the invariant the flag assumes.
#
# See MAC_HANDOFF.md, "Resuming a half-finished pass".
#
# Idempotent: safe to run again after an interruption. Verified on a copy
# before first use - 2,704 to run, 1,080 already-done rows preserved, 0 rows of
# the Windows shard touched.
set -e
cd "$(dirname "$0")/.."

MODEL="${MODEL:-qwen3:8b}"
SHARD="${SHARD:-shards/mac.txt}"
PY=./backend/.venv/bin/python3

# A copy before mutating anything. Skipped if one is already there, so a second
# run cannot overwrite the pristine backup with a half-finished state.
if [ ! -f data/claims.pre-resume-backup.db ]; then
    "$PY" -c "
import sqlite3
s=sqlite3.connect('data/claims.db'); d=sqlite3.connect('data/claims.pre-resume-backup.db')
s.backup(d); d.close(); s.close(); print('backup -> data/claims.pre-resume-backup.db')"
else
    echo "backup already present, keeping it"
fi

ollama ps >/dev/null 2>&1 || { echo "starting ollama..."; nohup ollama serve >/dev/null 2>&1 & sleep 3; }

MODEL="$MODEL" SHARD="$SHARD" "$PY" - <<'PY'
import os, sqlite3
model, shard = os.environ["MODEL"], os.environ["SHARD"]
keys = ' '.join(l for l in open(shard) if not l.startswith('#')).split()
ph = ','.join('?' * len(keys))
c = sqlite3.connect('data/claims.db')
n = c.execute(f"""UPDATE claim_papers SET direction = NULL
                   WHERE claim_key IN ({ph})
                     AND (evaluated_by IS NULL OR evaluated_by != ?)""",
              keys + [model]).rowcount
c.commit()
todo, kept = (c.execute(f"""SELECT COUNT(*) FROM claim_papers WHERE claim_key IN ({ph})
                             AND (direction IS NULL OR direction = '')""", keys).fetchone()[0],
              c.execute(f"""SELECT COUNT(*) FROM claim_papers WHERE claim_key IN ({ph})
                             AND evaluated_by = ?""", keys + [model]).fetchone()[0])
print(f"reset {n} rows | {kept} already judged by {model} are kept | resuming {todo}")
PY

exec caffeinate -dims "$PY" -u backend/evaluate_claims.py \
     $(grep -v '^#' "$SHARD") --stale --model "$MODEL"
