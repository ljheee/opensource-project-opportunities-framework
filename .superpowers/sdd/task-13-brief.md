### Task 13: 工程杂项（run 脚本分治 + filter --limit + 循环 + .gitignore）

**Files:**
- Modify: `.gitignore:18-21`
- Modify: `framework/stages/filter.py:214-221`（main）
- Modify: `run.sh:29-39`、`run.sh:57-64`
- Modify: `run_bulk.sh:30-40`、`run_bulk.sh:64-66`

**Interfaces:**
- Produces: `filter.py --limit N`（默认 50）；`run_filter(db, dry_run, limit)`

- [ ] **Step 1: .gitignore 删除两条**

删除第 18 行 `data/*.db` 和第 20 行 `data/reports/*.md`（保留 `!data/.gitkeep` 与 `!data/reports/.gitkeep` 无害，可一并删除）。验证：

```bash
git check-ignore data/framework.db data/reports/2099-01-01.md; echo "exit=$?"
```

Expected: `exit=1`（不再被忽略）

- [ ] **Step 2: filter.py 加 --limit**

filter.py:28 的 `get_discovered_projects(db: Database, limit: int = 50)` 已支持参数；`run_filter`（filter.py:164）签名改为：

```python
def run_filter(db: Database, dry_run: bool = False, limit: int = 50):
```

函数内 `projects = get_discovered_projects(db)` 改为 `get_discovered_projects(db, limit=limit)`。

`main()`（filter.py:214-221）改为：

```python
def main():
    parser = argparse.ArgumentParser(description="Semantic filtering for AI projects")
    parser.add_argument('--dry-run', action='store_true',
                        help="Don't write to database")
    parser.add_argument('--limit', type=int, default=50,
                        help="Max projects to classify per invocation")
    args = parser.parse_args()

    if args.limit <= 0:
        print("ERROR: limit must be a positive integer")
        sys.exit(1)

    db = Database()
    run_filter(db, dry_run=args.dry_run, limit=args.limit)
```

- [ ] **Step 3: run.sh / run_bulk.sh 本地改动分治**

两个脚本中现有的"检测本地未提交修改 → 丢弃"段（run.sh:31-37、run_bulk.sh:32-38）替换为：

```bash
# Detect local uncommitted changes: code/config changes abort; data/-only changes are
# pipeline artifacts (self-heal path after failed push) and are discarded as before.
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
```

（注意：删掉原有的 `git reset HEAD` + 全量 `git checkout -- .` 两行；`checkout HEAD -- data/` 已覆盖 staged 清理，无需保留 reset。）

- [ ] **Step 4: 两个脚本的 filter 调用改循环**

run.sh:59-64 与 run_bulk.sh:64-66 的单次 filter 调用替换为循环（上限取 config 的 bulk.max_per_day=100）：

```bash
  echo "Running semantic filter..."
  _FILTER_ROUNDS=0
  while [ "$(sqlite3 -noheader "$DB" "SELECT COUNT(*) FROM projects WHERE status='discovered';" 2>/dev/null || echo 0)" -gt 0 ] && [ "$_FILTER_ROUNDS" -lt 2 ]; do
    python3 "$FRAMEWORK_DIR/framework/stages/filter.py" --limit 100
    _FILTER_ROUNDS=$((_FILTER_ROUNDS + 1))
  done
```

（每轮 --limit 100 即 max_per_day，2 轮封顶 200/天，防死循环；backlog 巨大时多日消化。）

- [ ] **Step 5: 验证（spec §4 验证项 10，两场景真实执行）**

```bash
bash -n run.sh && bash -n run_bulk.sh && echo "syntax OK"

# 场景1：含代码改动 -> 必须在 [0/6] 处 exit 1
# （制造一个临时代码改动）
echo "# tmp" >> framework/__init__.py
./run.sh 2>&1 | head -8; echo "exit=${PIPESTATUS[0]:-$?}"
git checkout -- framework/__init__.py

# 场景2：仅 data/ 改动（含 staged）-> 应 WARN 后继续（不 exit 1）
touch data/tmp_probe.txt
git add data/tmp_probe.txt 2>/dev/null || true
git rm --cached data/tmp_probe.txt -q 2>/dev/null; rm -f data/tmp_probe.txt
# 用已跟踪的 data/reports 文件模拟 staged 改动
echo "probe" >> data/reports/2026-04-22.md && git add data/reports/2026-04-22.md
timeout 30 ./run.sh 2>&1 | head -6; echo "exit=$?"
# 确认 staged 探测改动已被 checkout HEAD 清除
git diff --cached --name-only | grep -q "data/reports/2026-04-22.md" && echo "FAIL: staged 未清理" || echo "staged cleanup OK"
git checkout HEAD -- data/reports/2026-04-22.md 2>/dev/null || true
```

Expected: `syntax OK`；场景1 输出 `ERROR: Uncommitted code/config changes detected` 且 exit=1；场景2 输出 `WARN: Uncommitted data/ changes` 且不 exit 1（30s timeout 会截断后续 pipeline，属预期）；`staged cleanup OK`

- [ ] **Step 6: Commit**

```bash
git add .gitignore framework/stages/filter.py run.sh run_bulk.sh
git commit -m "fix: abort on code changes in run scripts, loop filter with --limit, unignore data artifacts"
```

---

## 最终全链路验证（spec §4）

- [ ] **V1**: `./run.sh` 无 LLM 完整跑通：确认新 topics 查询生效、回溯日志出现（`Backfilled N days`）、无 LLM 分析 opportunities 为空、analyzer_version 标记正确
- [ ] **V2**: 运行前后实测速率消耗（spec §4 验证项 3 + §2.5 预算）：

```bash
TOKEN=$(grep GITHUB_TOKEN .env | cut -d= -f2 | tr -d '"')
curl -s -H "Authorization: Bearer $TOKEN" https://api.github.com/rate_limit | python3 -c "import json,sys; r=json.load(sys.stdin)['resources']['core']; print('before:', r['remaining'])"
./run.sh   # 或单独 python3 framework/stages/discover.py
curl -s -H "Authorization: Bearer $TOKEN" https://api.github.com/rate_limit | python3 -c "import json,sys; r=json.load(sys.stdin)['resources']['core']; print('after:', r['remaining'])"
```

Expected: 消耗量（before−after）符合 §2.5 预算（稳态 ~400-500，含存量回溯的首日 ~600-1200）；`sqlite3 data/framework.db "SELECT COUNT(*) FROM star_history WHERE sampled_at < date('now')"` 有合成行；discover 日志无长时间 rate limit 等待
- [ ] **V3**: `USE_LLM=true CLI_TOOL="claude --dangerously-skip-permissions" python3 framework/stages/analyze.py --date $(date -u +%Y-%m-%d) --use-llm --max-tasks 1`：确认 LLM 分析产出与项目实际相关的机会
- [ ] **V4**: `python3 framework/stages/validate.py --metrics-only` 与 `python3 framework/stages/reweight.py --dry-run` 均不崩
- [ ] **V5**: 连续两天跑 `./run.sh`：确认 active 项目不再每天重复生成 incremental 任务（spec §4 验证项 8）
- [ ] **V6（上线后 7 天观察项）**: 观察基于合成历史评分的项目 FP 表现（spec §4 验证项 9）：`sqlite3 data/framework.db "SELECT project_id, overall_score FROM early_burst_signals WHERE signals_json LIKE '%\"synthetic_history\": true%' ORDER BY calculated_at DESC LIMIT 20;"` —— 若这批项目后续集中被 validate 判为 false_positive，说明 unstar 低估偏差影响过大，需重新评估回溯策略
- [ ] **V7（网络相关遗留项）**: 开发机所在网络对 `/repos/{}/stargazers` 端点返回 404（网关限制，commits/readme/search 均正常），Task 3 的 stargazers 真实链路 E2E 无法在本地完成。合并后首次 GitHub Actions 运行时，检查 workflow 日志中的 `Backfilled N days` 行确认回溯在 CI 网络下生效；若 CI 也失败，排查 endpoint 可用性并考虑 GraphQL 替代

## 执行前置条件

1. **当前工作区有 11 个 framework 文件的未提交修改**（git status 可见）。Task 1 开始前必须 `git add -A && git commit`（或确认这些改动废弃后 `git checkout -- .`），否则 Task 13 的 run.sh 分治逻辑会误判，且各任务 commit 会混入无关改动。
2. `.env` 中 `GITHUB_TOKEN` 已配置（Task 2/3/5/9 的真实 API 验证依赖）。
3. 临时验证脚本统一放 `/tmp`，不提交仓库。

<!-- PLAN-END -->







