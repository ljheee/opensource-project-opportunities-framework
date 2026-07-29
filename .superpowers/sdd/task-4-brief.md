### Task 4: 回溯挂载 + 每日预算 + synthetic_history 标记

**Files:**
- Modify: `framework/stages/discover.py:313-438`（`_calculate_and_store_burst_score`）
- Modify: `framework/stages/discover.py:664-715`（`run()` 的存储与存量采样段）

**Interfaces:**
- Consumes: `_backfill_star_history(project_id, stars, conn)`（Task 3）
- Produces: `early_burst_signals.signals_json` 中新增 `"synthetic_history": bool`；每日回溯量受 `backfill_max_per_day` 限制

- [ ] **Step 1: `__init__` 增加当日回溯计数器**

`DiscoverStage.__init__` 末尾（Task 2 加的 `self.created_within_days` 之后）追加：

```python
        self._backfills_done = 0
```

- [ ] **Step 2: 加预算守卫方法**

在 `_backfill_star_history` 之后插入：

```python
    def _backfill_within_budget(self, project_id: str, stars: int, conn) -> int:
        """Backfill one project if the daily budget allows. Returns rows written."""
        budget = self.config.get_backfill_config()['max_per_day']
        if self._backfills_done >= budget:
            return 0
        written = self._backfill_star_history(project_id, stars, conn=conn)
        if written > 0:
            self._backfills_done += 1
        return written
```

- [ ] **Step 3: 新项目入库流程挂载**

`run()` 的存储循环（discover.py:669-684）中，`_sample_star_count` **之前**插入回溯调用（必须先回溯再采样，保证"无历史"判定有效）：

```python
                    project_id = self._upsert_project(
                        item['repo'], item['source'], item['signal'],
                        conn=conn
                    )
                    stored_count += 1
                    new_stars = (item.get('repo') or {}).get('stargazers_count') or 0
                    self._backfill_within_budget(project_id, new_stars, conn=conn)
                    self._sample_star_count(
                        project_id,
                        new_stars,
                        conn=conn
                    )
```

- [ ] **Step 4: 存量采样循环挂载**

`run()` 的存量采样段（discover.py:695-707）中，`_sample_star_count` 之前同样插入：

```python
                    self._backfill_within_budget(proj['id'], proj_stars, conn=conn)
                    self._sample_star_count(proj['id'], proj_stars, conn=conn)
```

- [ ] **Step 5: `synthetic_history` 标记**

`_calculate_and_store_burst_score`（discover.py:410-432）的 `signals_json` 改为包含标记——判断依据：该项目 star_history 最早样本日期是否早于本项目 `first_seen_at` 日期（早于则说明是回溯合成的）。把 `json.dumps({...})` 改为：

```python
                json.dumps({
                    'stars_7d_ago': stars_7d_ago,
                    'stars_14d_ago': stars_14d_ago,
                    'stars_21d_ago': stars_21d_ago,
                    'stars_30d_ago': stars_30d_ago,
                    'current_stars': current_stars,
                    'synthetic_history': bool(
                        history and proj['first_seen_at']
                        and min(h['sampled_at'] for h in history) < str(proj['first_seen_at'])[:10]
                    ),
                })
```

- [ ] **Step 6: 预算行为验证（真实运行，小预算）**

```bash
# 临时把 backfill_max_per_day 改为 2 跑一次 discover，观察日志
python3 - <<'EOF'
import yaml
cfg = yaml.safe_load(open('config.yaml'))
cfg['sources']['github']['backfill_max_per_day'] = 2
yaml.safe_dump(cfg, open('/tmp/config_test.yaml', 'w'), allow_unicode=True, sort_keys=False)
EOF
PYTHONPATH=. GITHUB_TOKEN=$(grep GITHUB_TOKEN .env | cut -d= -f2 | tr -d '"') python3 -c "
from framework.core.config_loader import ConfigLoader
from framework.core.db import Database
from framework.stages.discover import DiscoverStage
s = DiscoverStage(ConfigLoader('/tmp/config_test.yaml'), Database())
# 直接驱动预算守卫：挑 3 个无历史项目
conn = s.db.get_conn()
rows = conn.execute('''SELECT p.id, p.stars FROM projects p
  WHERE NOT EXISTS (SELECT 1 FROM star_history h WHERE h.project_id = p.id) LIMIT 3''').fetchall()
for r in rows:
    n = s._backfill_within_budget(r['id'], r['stars'] or 0, conn)
    print(r['id'], '->', n, 'rows')
conn.close()
assert s._backfills_done <= 2, s._backfills_done
print('budget OK, backfills done:', s._backfills_done)
"
```

Expected: 前 2 个项目写入 >0 行（有 star 的），第 3 个返回 0；输出 `budget OK`

- [ ] **Step 7: Commit**

```bash
git add framework/stages/discover.py
git commit -m "feat: wire star-history backfill into ingest with daily budget and synthetic flag"
```

