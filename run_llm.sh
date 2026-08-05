#!/usr/bin/env bash
# 每日本地 LLM 深度分析：对 early-burst 头部项目跑证据化 LLM 分析并推送结果。
# 建议 crontab（CI 在 12:00-12:40 北京时间跑完后执行）：
#   0 13 * * * /path/to/repo/run_llm.sh >> /path/to/repo/data/llm_top.log 2>&1
set -euo pipefail

FRAMEWORK_DIR="$(cd "$(dirname "$0")" && pwd)"
DB="$FRAMEWORK_DIR/data/framework.db"

if [ -f "$FRAMEWORK_DIR/.env" ]; then
  set -a; source "$FRAMEWORK_DIR/.env"; set +a
fi

if [ "${USE_LLM:-false}" != "true" ]; then
  echo "ERROR: USE_LLM=true required in .env"; exit 1
fi

echo "=== LLM Top-N run $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
if ! git -C "$FRAMEWORK_DIR" pull --rebase; then
  if git -C "$FRAMEWORK_DIR" rev-parse -q --verify REBASE_HEAD >/dev/null 2>&1; then
    echo "ERROR: rebase conflict (likely data/framework.db vs remote). Aborting; resolve manually."
    git -C "$FRAMEWORK_DIR" rebase --abort
    exit 1
  fi
  echo "WARN: pull failed (network?), continuing local"
fi
python3 "$FRAMEWORK_DIR/framework/stages/init_db.py"
python3 "$FRAMEWORK_DIR/framework/stages/llm_top.py" --max "${LLM_TOP_MAX:-5}"

sqlite3 "$DB" "PRAGMA wal_checkpoint(TRUNCATE);" >/dev/null 2>&1 || true
git -C "$FRAMEWORK_DIR" add "$DB"
git -C "$FRAMEWORK_DIR" diff --staged --quiet || \
  git -C "$FRAMEWORK_DIR" commit -m "feat: llm top analysis $(date -u +%Y-%m-%d)"

_push_ok=0
for _i in 1 2 3; do
  if git -C "$FRAMEWORK_DIR" push; then _push_ok=1; break; fi
  echo "WARN: push failed (attempt $_i/3), pull --rebase then retry..."
  sleep 10
  if ! git -C "$FRAMEWORK_DIR" pull --rebase; then
    if git -C "$FRAMEWORK_DIR" rev-parse -q --verify REBASE_HEAD >/dev/null 2>&1; then
      echo "ERROR: rebase conflict during push retry; aborting. Local commits kept for next run."
      git -C "$FRAMEWORK_DIR" rebase --abort
    fi
    break
  fi
done
[ "$_push_ok" -eq 0 ] && echo "ERROR: push failed; next run will retry from local commits"
echo "=== Done ==="
