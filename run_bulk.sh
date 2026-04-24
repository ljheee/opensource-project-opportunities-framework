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

# Git pull
git -C "$FRAMEWORK_DIR" pull --rebase 2>/dev/null || true

# Initialize DB
python3 "$FRAMEWORK_DIR/framework/stages/init_db.py"

# Discovery (if not skipped)
if [ "${SKIP_DISCOVERY:-false}" != "true" ]; then
  echo "Running discovery..."
  python3 "$FRAMEWORK_DIR/framework/stages/discover.py"
fi

# Check pending bulk projects
PENDING_BULK=$(sqlite3 "$DB" "SELECT COUNT(*) FROM projects WHERE status='discovered';" 2>/dev/null || echo "0")

echo "Pending bulk projects: $PENDING_BULK"

if [ "$PENDING_BULK" -eq 0 ]; then
  echo "No bulk projects pending. Switch to run.sh for incremental mode."
  exit 0
fi

# Stage 3: Filter pending projects
echo "Running semantic filter on pending projects..."
python3 "$FRAMEWORK_DIR/framework/stages/filter.py"

# Generate bulk tasks
python3 "$FRAMEWORK_DIR/framework/stages/schedule.py" --mode bulk --batch-size "$BATCH_SIZE"

# Get count of bulk tasks for today
BULK_TASKS=$(sqlite3 "$DB" "SELECT COUNT(*) FROM tasks WHERE task_date='$DATE' AND task_type='bulk' AND status='pending';" 2>/dev/null || echo "0")
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

# Git push
echo "Pushing changes..."
git -C "$FRAMEWORK_DIR" add "$DB" "$FRAMEWORK_DIR/data/reports/" 2>/dev/null || true
git -C "$FRAMEWORK_DIR" diff --staged --quiet || \
  git -C "$FRAMEWORK_DIR" commit -m "feat: bulk analysis $DATE ($BULK_TASKS tasks)"
git -C "$FRAMEWORK_DIR" push || true

echo "=== Complete ==="
