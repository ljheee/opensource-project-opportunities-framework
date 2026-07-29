### Task 1: config.yaml 新配置键 + ConfigLoader getter

**Files:**
- Modify: `config.yaml`
- Modify: `framework/core/config_loader.py`

**Interfaces:**
- Produces:
  - `ConfigLoader.get_created_within_days() -> int`（默认 730）
  - `ConfigLoader.get_backfill_config() -> Dict`（`{'max_pages': int 默认30, 'max_per_day': int 默认50}`）
  - Task 6/13 用到的 `scheduling.incremental` 新键在 Task 13 才消费，本任务只写配置

- [ ] **Step 1: 写失败验证**

```bash
PYTHONPATH=. python3 -c "
from framework.core.config_loader import ConfigLoader
c = ConfigLoader()
assert c.get_created_within_days() == 730, 'missing get_created_within_days'
bf = c.get_backfill_config()
assert bf['max_pages'] == 30 and bf['max_per_day'] == 50, bf
print('OK')
"
```

Expected: FAIL — `AttributeError: 'ConfigLoader' object has no attribute 'get_created_within_days'`

- [ ] **Step 2: 修改 config.yaml**

`sources.github` 段（第 34-43 行区域）的 `star_range` 后追加：

```yaml
    star_range: [50, 50000]
    created_within_days: 730
    backfill_max_pages: 30
    backfill_max_per_day: 50
```

`early_burst.metrics` 各组件 weight 改为：

```yaml
    star_velocity:
      weight: 0.45
    activity_index:
      weight: 0.35
    community_buzz:
      weight: 0.0
    novelty_signal:
      weight: 0.20
```

（各组件的 thresholds 子键保持不变）

`scheduling.incremental` 段改为：

```yaml
  incremental:
    max_per_day: 15
    star_change_threshold: 0.05
    recent_commit_days: 3
    min_reanalyze_days: 7
```

- [ ] **Step 3: config_loader.py 追加两个方法**

在 `get_star_range` 方法（约第 94-105 行）之后插入：

```python
    def get_created_within_days(self) -> int:
        raw = ((self.load().get('sources') or {}).get('github') or {}).get('created_within_days', 730)
        try:
            val = int(raw)
        except (ValueError, TypeError):
            return 730
        return val if val > 0 else 730

    def get_backfill_config(self) -> Dict:
        gh = ((self.load().get('sources') or {}).get('github') or {})
        def _pos_int(key, default):
            try:
                val = int(gh.get(key, default))
            except (ValueError, TypeError):
                return default
            return val if val > 0 else default
        return {
            'max_pages': _pos_int('backfill_max_pages', 30),
            'max_per_day': _pos_int('backfill_max_per_day', 50),
        }
```

- [ ] **Step 4: 重跑 Step 1 验证**

Expected: 输出 `OK`

- [ ] **Step 5: 权重迁移对比验证（spec §4 验证项 4）**

```bash
PYTHONPATH=. python3 -c "
from framework.core.config_loader import ConfigLoader
from framework.core.scoring_engine import ScoringEngine
se = ScoringEngine(ConfigLoader().get_early_burst_config())
r = se.calculate_overall(0.8, 0.7, 0.3, 0.5)
assert abs(r['overall_score'] - (0.8*0.45 + 0.7*0.35 + 0.5*0.20)) < 1e-9, r
print('weights OK:', round(r['overall_score'], 3))
"
```

Expected: 输出 `weights OK: 0.705`

- [ ] **Step 5b: 新旧权重翻转对比（spec §4 验证项 4）**

```bash
PYTHONPATH=. python3 - <<'EOF'
from framework.core.config_loader import ConfigLoader
from framework.core.db import Database
from framework.core.scoring_engine import ScoringEngine

db = Database()
conn = db.get_conn()
rows = conn.execute('''
    SELECT project_id, star_velocity_score, activity_index_score,
           community_buzz_score, novelty_score, overall_score, is_early_burst
    FROM (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY project_id ORDER BY calculated_at DESC) rn
        FROM early_burst_signals
    ) WHERE rn = 1
''').fetchall()
new_se = ScoringEngine(ConfigLoader().get_early_burst_config())
OLD_W = {'v': 0.35, 'a': 0.25, 'b': 0.25, 'n': 0.15}
flips = []
for r in rows:
    old_score = (r['star_velocity_score']*OLD_W['v'] + r['activity_index_score']*OLD_W['a']
                 + r['community_buzz_score']*OLD_W['b'] + r['novelty_score']*OLD_W['n'])
    new = new_se.calculate_overall(r['star_velocity_score'], r['activity_index_score'],
                                   r['community_buzz_score'], r['novelty_score'])
    old_burst = old_score >= 0.65
    if old_burst != new['is_early_burst']:
        flips.append((r['project_id'], round(old_score,3), round(new['overall_score'],3), old_burst))
print(f'{len(rows)} projects, {len(flips)} flips')
for f in flips[:20]:
    print(' ', f)
assert len(flips) <= max(2, len(rows) // 10), '翻转比例异常，检查权重配置'
print('weight migration OK')
EOF
```

Expected: 打印翻转名单（当前库 0 个 early-burst，预期翻转很少），输出 `weight migration OK`

- [ ] **Step 6: Commit**

```bash
git add config.yaml framework/core/config_loader.py
git commit -m "feat: add discovery/backfill config keys, renormalize scoring weights (buzz out)"
```

