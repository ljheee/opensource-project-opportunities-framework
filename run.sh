#!/usr/bin/env bash
set -euo pipefail

FRAMEWORK_DIR="$(cd "$(dirname "$0")" && pwd)"
DB="$FRAMEWORK_DIR/data/framework.db"
DATE=$(date -u +%Y-%m-%d)

# Load environment
if [ -f "$FRAMEWORK_DIR/.env" ]; then
  set -a; source "$FRAMEWORK_DIR/.env"; set +a
fi

echo "=== AI Project Opportunities Framework - $DATE ==="

# Stage 0: Git pull
echo "[0/6] git pull..."
git -C "$FRAMEWORK_DIR" pull --rebase 2>/dev/null || true

# Stage 1: Initialize DB
echo "[1/6] Initializing database..."
python3 "$FRAMEWORK_DIR/framework/stages/init_db.py"

# Stage 2: Discovery (if not run via CI)
if [ "${SKIP_DISCOVERY:-false}" != "true" ]; then
  echo "[2/6] Stage 2: Discovery..."
  python3 "$FRAMEWORK_DIR/framework/stages/discover.py"
else
  echo "[2/6] Skipping discovery (SKIP_DISCOVERY=true)"
fi

# Stage 3: Semantic filtering
FILTER_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM projects WHERE status='discovered';" 2>/dev/null || echo "0")

if [ "$FILTER_COUNT" -gt 0 ]; then
  echo "[3/6] Stage 3: Semantic filtering ($FILTER_COUNT projects)..."
  python3 "$FRAMEWORK_DIR/framework/stages/filter.py"
else
  echo "[3/6] No projects to filter, skipping."
fi

# Stage 4: Schedule tasks
echo "[4/6] Stage 4: Scheduling tasks..."
python3 "$FRAMEWORK_DIR/framework/stages/schedule.py" --mode incremental

# Check pending tasks
PENDING=$(sqlite3 "$DB" "SELECT COUNT(*) FROM tasks WHERE task_date='$DATE' AND status='pending';" 2>/dev/null || echo "0")

if [ "$PENDING" -eq 0 ]; then
  echo "[5/6] No pending tasks. Generating report..."
  python3 "$FRAMEWORK_DIR/framework/stages/report.py" --date "$DATE"
  echo "[6/6] Complete."
  exit 0
fi

echo "Pending tasks: $PENDING"

# Stage 5: LLM Analysis
echo "[5/6] Stage 5: LLM Analysis ($PENDING projects)..."
if [ "${USE_LLM:-false}" = "true" ]; then
  python3 "$FRAMEWORK_DIR/framework/stages/analyze.py" --date "$DATE" --max-tasks 15 --use-llm
else
  python3 "$FRAMEWORK_DIR/framework/stages/analyze.py" --date "$DATE" --max-tasks 15
fi

# Stage 6: Generate report
echo "[6/6] Generating report..."
python3 "$FRAMEWORK_DIR/framework/stages/report.py" --date "$DATE"

# Git push
echo "Pushing changes..."
git -C "$FRAMEWORK_DIR" add "$DB" "$FRAMEWORK_DIR/data/reports/" 2>/dev/null || true
git -C "$FRAMEWORK_DIR" diff --staged --quiet || \
  git -C "$FRAMEWORK_DIR" commit -m "feat: daily report $DATE"
git -C "$FRAMEWORK_DIR" push || true

echo "=== Complete ==="
echo "Report: $FRAMEWORK_DIR/data/reports/$DATE.md"
