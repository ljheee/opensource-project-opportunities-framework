#!/usr/bin/env bash
set -euo pipefail

FRAMEWORK_DIR="$(cd "$(dirname "$0")" && pwd)"
DB="$FRAMEWORK_DIR/data/framework.db"
BATCH_SIZE="${1:-20}"
DATE=$(date -u +%Y-%m-%d)

# Load environment
if [ -f "$FRAMEWORK_DIR/.env" ]; then
  set -a; source "$FRAMEWORK_DIR/.env"; set +a
fi

echo "=== Bulk Processing - $DATE (batch=$BATCH_SIZE) ==="

# Process lock: shared with run.sh to prevent concurrent DB access
_LOCK_FILE="$FRAMEWORK_DIR/data/.framework.lock"
mkdir -p "$(dirname "$_LOCK_FILE")"
if command -v flock >/dev/null 2>&1; then
  exec 9>"$_LOCK_FILE"
  if ! flock -n 9; then
    echo "ERROR: Another framework instance (run.sh or run_bulk.sh) is already running. Exiting."
    echo "       If you are sure no other instance is running, remove the lock file: rm $_LOCK_FILE"
    exit 1
  fi
else
  echo "WARN: flock command not available (macOS), skipping process lock. Do not run multiple framework instances concurrently."
fi

# Detect local uncommitted changes: code/config changes abort; data/-only changes are
# pipeline artifacts (self-heal path after failed push) and are discarded as before.
echo "Git pull..."
_LOCAL_CHANGES=$(git -C "$FRAMEWORK_DIR" diff --name-only HEAD 2>/dev/null || true)
if [ -n "$_LOCAL_CHANGES" ]; then
  _CODE_CHANGES=$(echo "$_LOCAL_CHANGES" | grep -v '^data/' || true)
  if [ -n "$_CODE_CHANGES" ]; then
    echo "ERROR: Uncommitted code/config changes detected. Commit or stash them first:"
    echo "$_CODE_CHANGES" | sed 's/^/  /'
    echo "       Recovery: git add -A && git commit, or git stash"
    exit 1
  fi
  echo "WARN: Uncommitted data/ changes detected (likely from a previous failed push). Discarding:"
  echo "$_LOCAL_CHANGES" | sed 's/^/  /'
  # checkout HEAD -- 同时清理 staged 与工作区（崩溃在 git add 之后 commit 之前时，
  # data/ 改动处于 staged 状态，单纯 checkout -- 清不掉 index，会导致 pull --rebase 失败）
  git -C "$FRAMEWORK_DIR" checkout HEAD -- data/ 2>/dev/null || true
fi
git -C "$FRAMEWORK_DIR" pull --rebase || \
  echo "WARN: git pull --rebase failed, continuing with local state (may be missing remote changes)."

# Initialize DB
python3 "$FRAMEWORK_DIR/framework/stages/init_db.py"

# Crash recovery: repair stale analyzing status and orphan records
PYTHONPATH="$FRAMEWORK_DIR" python3 -c "from framework.core.db import Database; db = Database(); db.repair_analyzing_status(); db.repair_orphan_records()"

# Discovery (if not skipped)
if [ "${SKIP_DISCOVERY:-false}" != "true" ]; then
  echo "Running discovery..."
  python3 "$FRAMEWORK_DIR/framework/stages/discover.py"
fi

# Check pending bulk projects
PENDING_BULK=$(sqlite3 -noheader "$DB" "SELECT COUNT(*) FROM projects WHERE status='discovered';" 2>/dev/null || echo "0")

echo "Pending bulk projects: $PENDING_BULK"

if [ "$PENDING_BULK" -eq 0 ]; then
  echo "No bulk projects pending. Switch to run.sh for incremental mode."
  exit 0
fi

# Stage 3: Filter pending projects (loop with --limit 100 per round, max 2 rounds
# to drain backlog without risking an infinite loop)
echo "Running semantic filter on pending projects..."
_FILTER_ROUNDS=0
while [ "$(sqlite3 -noheader "$DB" "SELECT COUNT(*) FROM projects WHERE status='discovered';" 2>/dev/null || echo 0)" -gt 0 ] && [ "$_FILTER_ROUNDS" -lt 2 ]; do
  python3 "$FRAMEWORK_DIR/framework/stages/filter.py" --limit 100
  _FILTER_ROUNDS=$((_FILTER_ROUNDS + 1))
done

# Generate bulk tasks
python3 "$FRAMEWORK_DIR/framework/stages/schedule.py" --mode bulk --batch-size "$BATCH_SIZE"

# Get count of bulk tasks for today
BULK_TASKS=$(sqlite3 -noheader "$DB" "SELECT COUNT(*) FROM tasks WHERE task_date='$DATE' AND task_type='bulk' AND status='pending';" 2>/dev/null || echo "0")
echo "Bulk tasks to analyze: $BULK_TASKS"

# Stage 4: LLM Analysis (bulk mode)
if [ "$BULK_TASKS" -gt 0 ]; then
  echo "Running LLM analysis on bulk tasks..."
  if [ "${USE_LLM:-false}" = "true" ]; then
    python3 "$FRAMEWORK_DIR/framework/stages/analyze.py" --date "$DATE" --max-tasks "$BATCH_SIZE" --use-llm
  else
    python3 "$FRAMEWORK_DIR/framework/stages/analyze.py" --date "$DATE" --max-tasks "$BATCH_SIZE"
  fi
fi

# Stage 5: Generate report
python3 "$FRAMEWORK_DIR/framework/stages/report.py" --date "$DATE"

# Ensure WAL is checkpointed before git add so .db file is self-contained
sqlite3 "$DB" "PRAGMA wal_checkpoint(TRUNCATE);" >/dev/null 2>&1 || true

# Git push with 3-retry resilience
echo "Pushing changes..."
git -C "$FRAMEWORK_DIR" add "$DB" "$FRAMEWORK_DIR/data/reports/" 2>/dev/null || true
git -C "$FRAMEWORK_DIR" diff --staged --quiet || \
  git -C "$FRAMEWORK_DIR" commit -m "feat: bulk analysis $DATE ($BULK_TASKS tasks)"

_push_ok=0
for _i in 1 2 3; do
  if git -C "$FRAMEWORK_DIR" push; then
    _push_ok=1
    break
  fi
  echo "WARN: git push failed (attempt $_i/3), sleeping 10s then pull --rebase before retry..."
  sleep 10
  git -C "$FRAMEWORK_DIR" pull --rebase || true
done
if [ "$_push_ok" -eq 0 ]; then
  echo "ERROR: git push failed 3 times in a row. Please manually push: cd $FRAMEWORK_DIR && git pull --rebase && git push"
fi

echo "=== Complete ==="
