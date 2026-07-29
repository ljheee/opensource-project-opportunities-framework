### Task 3: L1 挂载（预算 + 触发 + fail_count + 评分流程接线）

**Files:**
- Modify: `framework/stages/discover.py`（`__init__`、新增 `_structure_within_budget`、`_calculate_and_store_burst_score` 采集调用点）

**Interfaces:**
- Consumes: `_fetch_structure_facts(full_name)`（Task 2）、`ConfigLoader.get_structure_max_per_day()`（Task 1）
- Produces: `_structure_within_budget(project_id: str, conn) -> Optional[Dict]` — 本项目本轮新采集则返回 facts dict，否则返回 None；Task 7 的评分接线依赖此返回值与 `projects.structure_json` 列

- [ ] **Step 1: `__init__` 加计数器**

`self._backfills_done = 0` 之后追加：

```python
        self._structures_done = 0
```

- [ ] **Step 2: 实现预算守卫方法**

在 `_fetch_structure_facts` 之后插入：

```python
    def _structure_within_budget(self, project_id: str, conn) -> Optional[Dict]:
        """Fetch L1 structure facts for one project if due and within budget.

        Returns the facts dict if freshly fetched this call, else None.
        Freshness: structure_json missing / fetched_at NULL / fetched_at older
        than 10 days. Failure gating: 3 consecutive failures -> skip for 30 days.
        """
        row = conn.execute(
            'SELECT structure_json FROM projects WHERE id = ?', (project_id,)
        ).fetchone()
        existing = None
        if row and row['structure_json']:
            try:
                existing = json.loads(row['structure_json'])
            except (json.JSONDecodeError, TypeError):
                existing = None
        now = datetime.now(timezone.utc)
        if existing and existing.get('fetched_at'):
            try:
                fetched = datetime.fromisoformat(str(existing['fetched_at']).replace('Z', '+00:00'))
                if fetched.tzinfo is None:
                    fetched = fetched.replace(tzinfo=timezone.utc)
                if (now - fetched).days < 10:
                    return None  # fresh enough
            except (ValueError, TypeError):
                pass
        # Failure gating: 3 consecutive failures -> 30-day cooldown
        if existing and not existing.get('fetched_at'):
            try:
                fail_count = int(existing.get('fail_count') or 0)
            except (ValueError, TypeError):
                fail_count = 0
            last_fail = existing.get('last_fail_at')
            if fail_count >= 3 and last_fail:
                try:
                    lf = datetime.fromisoformat(str(last_fail).replace('Z', '+00:00'))
                    if lf.tzinfo is None:
                        lf = lf.replace(tzinfo=timezone.utc)
                    if (now - lf).days < 30:
                        return None
                except (ValueError, TypeError):
                    pass
        budget = self.config.get_structure_max_per_day()
        if self._structures_done >= budget:
            return None
        facts = self._fetch_structure_facts(project_id)
        self._structures_done += 1
        if facts is None:
            prev_fail = 0
            if existing:
                try:
                    prev_fail = int(existing.get('fail_count') or 0)
                except (ValueError, TypeError):
                    prev_fail = 0
            # 保留旧的成功事实（若存在），只更新失败计数——刷新失败
            # 不应销毁仍可用的旧数据（review 修正）
            failure_record = dict(existing) if existing else {}
            failure_record['fetched_at'] = (existing or {}).get('fetched_at')
            failure_record['fail_count'] = prev_fail + 1
            failure_record['last_fail_at'] = now.isoformat()
            conn.execute(
                'UPDATE projects SET structure_json = ? WHERE id = ?',
                (json.dumps(failure_record, ensure_ascii=False), project_id)
            )
            return None
        facts['fetched_at'] = now.isoformat()
        facts['fail_count'] = 0
        conn.execute(
            'UPDATE projects SET structure_json = ? WHERE id = ?',
            (json.dumps(facts, ensure_ascii=False), project_id)
        )
        return facts
```

- [ ] **Step 3: 评分流程接线**

`_calculate_and_store_burst_score` 中，**open_issues 解析块之后、activity 计算之前**插入一行（review 修正：原位置在 activity 调用点之后会造成 NameError）：

```python
            fresh_facts = self._structure_within_budget(project_id, conn)
```

（排队说明：本任务按 run() 既有顺序处理——新项目 store 循环在前、存量循环在后，故新发现项目自然优先。**已知偏离（spec §2.1 排队条款）**：存量按表序而非显式 fetched_at 最旧优先，接受理由：10 天刷新周期下偏差 ≤1 天，影响可忽略。预算计数语义：**无论成败均计预算**（防限流保护，与 backfill 仅成功计数不同，属有意为之——失败项目重试也消耗 API）。`fresh_facts` 变量供 Task 7 的评分接线使用。）

- [ ] **Step 4: 逻辑验证（monkeypatch，无网络）**

```bash
rm -f /tmp/t3_test.db*; PYTHONPATH=. python3 - <<'EOF'
from framework.core.config_loader import ConfigLoader
from framework.core.db import Database
from framework.stages.discover import DiscoverStage

db = Database('/tmp/t3_test.db'); db.init_tables()
conn = db.get_conn()
for i in range(3):
    conn.execute("INSERT INTO projects (id, name, status) VALUES (?, 'x', 'discovered')", (f'a/p{i}',))
conn.commit()

s = DiscoverStage(ConfigLoader(), Database())
calls = []
s._fetch_structure_facts = lambda pid: calls.append(pid) or {'has_tests': True, 'issue_health': None, 'top_issues': []} if pid != 'a/p2' else None

# 预算内：p0/p1 成功采集；p2 因预算耗尽（budget=2）不被尝试
s.config.get_structure_max_per_day = lambda: 2
r0 = s._structure_within_budget('a/p0', conn)
r1 = s._structure_within_budget('a/p1', conn)
r2 = s._structure_within_budget('a/p2', conn)
assert r0 is not None and r0['has_tests'] is True
assert r1 is not None
assert r2 is None and 'a/p2' not in calls, calls
# 失败路径：恢复预算，让 p2 真实失败一次，fail_count=1 写库且保留语义正确
s.config.get_structure_max_per_day = lambda: 50
calls.clear()
r2b = s._structure_within_budget('a/p2', conn)
assert r2b is None and 'a/p2' in calls
import json as j
row = conn.execute("SELECT structure_json FROM projects WHERE id='a/p2'").fetchone()
assert j.loads(row['structure_json'])['fail_count'] == 1, row['structure_json']
# 新鲜度：p0 刚采集过，再调应跳过
assert s._structure_within_budget('a/p0', conn) is None
# 失败计数：手工制造 3 次失败后应 30 天不重试
from datetime import datetime as _dt, timezone as _tz
conn.execute("UPDATE projects SET structure_json = ? WHERE id = 'a/p2'",
             (j.dumps({'fetched_at': None, 'fail_count': 3, 'last_fail_at': _dt.now(_tz).isoformat()}),))
conn.commit()
s._structures_done = 0
assert s._structure_within_budget('a/p2', conn) is None and 'a/p2' not in calls[2:]
conn.close()
print('budget/freshness/fail-gating OK')
EOF
```

Expected: 输出 `budget/freshness/fail-gating OK`

- [ ] **Step 5: Commit**

```bash
git add framework/stages/discover.py
git commit -m "feat: wire L1 structure fetch into scoring with budget, freshness, fail gating"
```

