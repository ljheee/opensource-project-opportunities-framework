### Task 7: 评分反哺（buzz 复活 + activity 增强 + reweight 组件表）

**Files:**
- Modify: `framework/core/scoring_engine.py`
- Modify: `framework/stages/discover.py:553`（buzz 调用点）、`:537-539`（activity 调用点）、signals_json 构造
- Modify: `framework/stages/reweight.py:20-25`

**Interfaces:**
- Consumes: `projects.structure_json`（Task 3）、`_structure_within_budget` 返回值（Task 3）
- Produces: `ScoringEngine.calculate_buzz(issue_health: Optional[Dict]) -> float`；`calculate_activity_index(open_issues, commit_frequency, pr_merge_rate=None, has_tests=None, has_ci=None)`；signals_json 新增 `buzz_source: "real" | "fallback"`

- [ ] **Step 1: 写失败验证**

```bash
PYTHONPATH=. python3 -c "
from framework.core.config_loader import ConfigLoader
from framework.core.scoring_engine import ScoringEngine
se = ScoringEngine(ConfigLoader().get_early_burst_config())
hot = se.calculate_buzz({'reaction_total': 80, 'avg_comments': 6.0, 'active_issues_30d': 6})
cold = se.calculate_buzz({'reaction_total': 0, 'avg_comments': 0.0, 'active_issues_30d': 0})
none = se.calculate_buzz(None)
assert hot > cold >= 0.0, (hot, cold)
assert none == se.default_buzz_score(), none
a1 = se.calculate_activity_index(10, 5.0, has_tests=True, has_ci=True)
a0 = se.calculate_activity_index(10, 5.0)
assert abs(a1 - min(a0 + 0.1, 1.0)) < 1e-9, (a0, a1)
print('scoring OK', hot, cold, none)
"
```

Expected: FAIL — `AttributeError: 'ScoringEngine' object has no attribute 'calculate_buzz'` 或 activity 参数 TypeError

- [ ] **Step 2: scoring_engine 实现**

`default_buzz_score` 之后插入：

```python
    def calculate_buzz(self, issue_health: Optional[Dict]) -> float:
        """Real community buzz from L1 issue health. None -> default fallback."""
        if not issue_health or not isinstance(issue_health, dict):
            return self.default_buzz_score()
        t = self._thresholds('community_buzz')
        def _f(key, default):
            try:
                return max(float(t.get(key, default)), 0.0001)
            except (ValueError, TypeError):
                return default
        reaction_score = min((issue_health.get('reaction_total') or 0) / _f('reaction_total_full', 50), 1.0)
        active_score = min((issue_health.get('active_issues_30d') or 0) / _f('active_issues_full', 5), 1.0)
        comments_score = min((issue_health.get('avg_comments') or 0) / _f('avg_comments_full', 5), 1.0)
        return min(reaction_score * 0.5 + active_score * 0.3 + comments_score * 0.2, 1.0)
```

`calculate_activity_index` 签名改为 `(self, open_issues, commit_frequency, pr_merge_rate=None, has_tests=None, has_ci=None)`，`return min(score, 1.0)` 之前插入：

```python
        if has_tests is not None or has_ci is not None:
            if has_tests and has_ci:
                score += 0.1
            elif has_tests or has_ci:
                score += 0.05
```

- [ ] **Step 3: discover 评分接线**

`_calculate_and_store_burst_score` 中，Task 3 加的 `fresh_facts = self._structure_within_budget(project_id, conn)` 行之后插入：

```python
            structure = None
            if fresh_facts:
                structure = fresh_facts
            elif proj['structure_json']:
                try:
                    structure = json.loads(proj['structure_json'])
                except (json.JSONDecodeError, TypeError):
                    structure = None
```

buzz 调用点改为：

```python
            issue_health = (structure or {}).get('issue_health')
            buzz_score = self.scoring.calculate_buzz(issue_health)
            buzz_source = 'real' if issue_health else 'fallback'
```

activity 调用点改为：

```python
            activity_score = self.scoring.calculate_activity_index(
                open_issues, commit_frequency,
                has_tests=(structure or {}).get('has_tests'),
                has_ci=(structure or {}).get('has_ci')
            )
```

signals_json 的 dict 中加一行：`'buzz_source': buzz_source,`

- [ ] **Step 4: reweight COMPONENTS 加回**

reweight.py:20-25 改为：

```python
COMPONENTS = ['star_velocity', 'activity_index', 'community_buzz', 'novelty_signal']
COMPONENT_COLS = {
    'star_velocity': 'star_velocity_at_pred',
    'activity_index': 'activity_index_at_pred',
    'community_buzz': 'community_buzz_at_pred',
    'novelty_signal': 'novelty_at_pred',
}
```

- [ ] **Step 5: 重跑 Step 1 验证 + reweight/validate 冒烟（spec §7 验证项 4/5）**

```bash
python3 framework/stages/reweight.py --dry-run && python3 framework/stages/validate.py --metrics-only >/dev/null && echo "smoke OK"
```

Expected: Step 1 输出 `scoring OK`；dry-run 走 MIN_SAMPLES 早退不崩；输出 `smoke OK`

- [ ] **Step 6: Commit**

```bash
git add framework/core/scoring_engine.py framework/stages/discover.py framework/stages/reweight.py
git commit -m "feat: revive buzz as real signal, enhance activity with tests/CI facts, restore buzz in reweight"
```

---

## 最终全链路验证（spec §7）

- [ ] **V1**: L1 真实采集：`python3 framework/stages/discover.py`（后台），日志出现 structure 采集且预算 ≤50；`sqlite3 data/framework.db "SELECT COUNT(*) FROM projects WHERE structure_json IS NOT NULL;"` > 0；抽查 3 个项目 structure_json 字段合理。另用 `PYTHONPATH=. python3 -c` 驱动 `_fetch_structure_facts` 打一个已知大型 monorepo（如 `microsoft/vscode`），断言返回 dict 的 `partial` 为 True 且 `core_paths == []`（truncated 降级负例，spec §7 验证项 1）
- [ ] **V2**: L1 幂等：同日二次跑 discover，`structure_json` 的 fetched_at 不变（不重复采集）
- [ ] **V3**: L2 程序化断言（spec §7 验证项 3）：`USE_LLM=true CLI_TOOL="claude --dangerously-skip-permissions" python3 framework/stages/analyze.py --date $(date -u +%Y-%m-%d) --use-llm --max-tasks 3` 后——若 3 个任务都有 core_paths，先手动挑 1 个 `core_paths_reason='no_match'` 的项目补跑（保证覆盖无参考集路径）：

```bash
PYTHONPATH=. python3 - <<'EOF'
import json
from framework.core.db import Database
conn = Database().get_conn()
rows = conn.execute("""
    SELECT a.evidence_json, p.structure_json FROM analyses a
    JOIN projects p ON a.project_id = p.id
    WHERE a.analyzer_version = 'llm-v1' AND a.evidence_json IS NOT NULL
    ORDER BY a.id DESC LIMIT 3
""").fetchall()
assert rows, 'no llm-v1 analyses with evidence'
for r in rows:
    ev = json.loads(r['evidence_json'])
    for k in ('innovation_evidence', 'problem_evidence', 'confidence', 'cannot_determine', 'validation'):
        assert k in ev, (k, ev)
    st = json.loads(r['structure_json']) if r['structure_json'] else {}
    core = st.get('core_paths') or []
    if core:
        tokens = core + [p.rsplit('/', 1)[-1] for p in core if '/' in p]
        for item in ev['innovation_evidence']:
            assert any(t.lower() in item.lower() for t in tokens), item
    if ev['cannot_determine']:
        assert ev['confidence'] != 'high', ev
print('L2 evidence assertions OK:', len(rows), 'analyses')
EOF
```

Expected: 输出 `L2 evidence assertions OK`
- [ ] **V4**: 反哺对比：挑 1 个已有 L1 数据的项目，对比其 buzz_source=real 的最新评分与历史 fallback 评分。注意：early_burst_signals 表中混存旧权重（0.45/0.35/0.0/0.20）与新权重（0.40/0.30/0.10/0.20）两个 regime 的行，横向对比整体分时注意口径（prediction_outcomes 实测 0 行，闭环不受影响）
- [ ] **V5**: `reweight.py --dry-run`、`validate.py --metrics-only` 不崩
- [ ] **V6**: 速率消耗观察：discover 日志无 rate limit 长等待

## 执行前置条件

1. 工作区应干净（`git status --short` 无代码改动）；data/ 下的 DB/报告改动属正常 pipeline 产物
2. `.env` 中 GITHUB_TOKEN 有效（L1/L2 真实抓取依赖）
3. 本机网络对 stargazers 404 属已知网关限制，不影响本计划（trees/issues/raw 已实测可用）




