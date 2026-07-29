### Task 12: scheduler incremental 冷静期 + 变化双约束

**Files:**
- Modify: `framework/core/scheduler.py:74-120`（`generate_incremental_tasks`）
- Modify: `framework/stages/schedule.py`（读取新配置键传入）

**Interfaces:**
- Consumes: config `scheduling.incremental` 新键（Task 1 已写入）：`star_change_threshold`、`recent_commit_days`、`min_reanalyze_days`
- Produces: active 项目仅当 "距最近 analysis ≥ min_reanalyze_days AND（7 日涨幅 ≥ 阈值 OR last_commit_at 在近 N 天）" 才生成任务；scheduled 项目判据改为 NOT EXISTS done task

- [ ] **Step 1: 写失败验证**

```bash
PYTHONPATH=. python3 - <<'EOF'
from datetime import datetime, timezone, timedelta
from framework.core.db import Database
from framework.core.scheduler import Scheduler

iso = lambda days_ago: (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
db = Database('/tmp/sched_test.db'); db.init_tables()
conn = db.get_conn()
# active 项目：昨天刚分析过（有 done task + analyses 行，时间用生产同款 ISO 格式），
# 涨幅巨大 —— 冷静期内，不应生成任务
conn.execute("INSERT INTO projects (id, name, stars, status, last_commit_at) VALUES ('a/x','x',1000,'active', ?)", (iso(0),))
conn.execute("INSERT INTO analyses (project_id, analyzed_at, overall_score) VALUES ('a/x', ?, 8)", (iso(1),))
conn.execute("INSERT INTO tasks (project_id, task_date, task_type, status) VALUES ('a/x', '2026-01-01', 'incremental', 'done')")
conn.execute("INSERT INTO star_history (project_id, sampled_at, stars) VALUES ('a/x', date('now','-7 days'), 100)")
conn.commit(); conn.close()
sch = Scheduler(db.db_path, {'incremental': {'star_change_threshold': 0.05, 'recent_commit_days': 3, 'min_reanalyze_days': 7}})
n = sch.generate_incremental_tasks('2099-01-01', 10)
assert n == 0, f'cooldown violated: {n} tasks'
print('cooldown OK')
EOF
```

Expected: FAIL — 当前实现无条件生成 1 个任务。**注意**：fixture 必须插 done task（否则按新 SQL 落入"从未分析放行"分支），且时间值必须用生产同款 `isoformat()`（含 'T' 和时区），否则测不出 datetime 格式比较问题。

- [ ] **Step 2: `generate_incremental_tasks` 查询重写**

scheduler.py:74-120 的方法体中，读取配置并替换候选 SQL：

```python
    def generate_incremental_tasks(self, date: str, max_tasks: int) -> int:
        if max_tasks <= 0:
            return 0
        inc = (self.config or {}).get('incremental') or {}
        try:
            star_threshold = float(inc.get('star_change_threshold', 0.05))
        except (ValueError, TypeError):
            star_threshold = 0.05
        try:
            recent_commit_days = int(inc.get('recent_commit_days', 3))
        except (ValueError, TypeError):
            recent_commit_days = 3
        try:
            cooldown_days = int(inc.get('min_reanalyze_days', 7))
        except (ValueError, TypeError):
            cooldown_days = 7

        conn = self.get_conn()
        try:
            cur = conn.execute('''
                SELECT p.id, COALESCE(e.overall_score, 0.5) as burst_score
                FROM projects p
                LEFT JOIN (
                    SELECT project_id, overall_score,
                           ROW_NUMBER() OVER (PARTITION BY project_id ORDER BY calculated_at DESC) as rn
                    FROM early_burst_signals
                ) e ON p.id = e.project_id AND e.rn = 1
                WHERE p.status IN ('scheduled', 'active')
                AND NOT EXISTS (
                    SELECT 1 FROM tasks t
                    WHERE t.project_id = p.id
                    AND t.task_type = 'incremental'
                    AND t.task_date = ?
                )
                AND NOT EXISTS (
                    SELECT 1 FROM tasks t
                    WHERE t.project_id = p.id
                    AND t.status IN ('pending', 'running')
                )
                AND (
                    -- Never analyzed: always eligible
                    NOT EXISTS (SELECT 1 FROM tasks t WHERE t.project_id = p.id AND t.status = 'done')
                    OR (
                        -- Cooldown elapsed since last analysis.
                        -- datetime() normalizes ISO 'T...+00:00' to SQLite 'YYYY-MM-DD HH:MM:SS';
                        -- COALESCE prevents starvation when a done task exists but analyses rows are gone.
                        COALESCE(
                            datetime((SELECT MAX(a.analyzed_at) FROM analyses a WHERE a.project_id = p.id)),
                            '1970-01-01'
                        ) <= datetime('now', '-' || ? || ' days')
                        AND (
                            -- 7-day star growth >= threshold (unknown history -> not satisfied)
                            (
                                SELECT CASE WHEN h.old_stars > 0
                                       THEN (CAST(p.stars AS REAL) - h.old_stars) / h.old_stars
                                       ELSE 0 END
                                FROM (
                                    SELECT stars as old_stars FROM star_history
                                    WHERE project_id = p.id
                                      AND sampled_at <= date('now', '-7 days')
                                    ORDER BY sampled_at DESC LIMIT 1
                                ) h
                            ) >= ?
                            OR datetime(p.last_commit_at) >= datetime('now', '-' || ? || ' days')
                        )
                    )
                )
                ORDER BY burst_score DESC, p.stars DESC, p.id ASC
                LIMIT ?
            ''', (date, cooldown_days, star_threshold, recent_commit_days, max_tasks))
```

（其余 INSERT 循环与现有代码相同，保持不变。）

注意：star_history 无 7 天前样本时子查询 `h` 为空 → 整个标量子查询为 NULL → `NULL >= ?` 为假，涨幅条件视为不满足，符合 spec fallback 定义。

- [ ] **Step 3: schedule.py 传入完整 scheduling 配置**

schedule.py:21 的 `Scheduler(db.db_path, config.get_scheduling_config())` 已传整个 scheduling dict（含 incremental 新键），**无需改动**——确认即可：

```bash
grep -n "Scheduler(db.db_path" framework/stages/schedule.py
```

Expected: 输出 `21:    scheduler = Scheduler(db.db_path, config.get_scheduling_config())`

- [ ] **Step 4: 重跑 Step 1 验证 + 放行用例**

```bash
PYTHONPATH=. python3 - <<'EOF'
from datetime import datetime, timezone, timedelta
from framework.core.db import Database
from framework.core.scheduler import Scheduler

iso = lambda days_ago: (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
db = Database('/tmp/sched_test2.db'); db.init_tables()
conn = db.get_conn()
# 每个项目都插 done task + analyses 行（ISO 格式），避免落入"从未分析放行"分支
# 案例A：active、10 天前分析、7 日涨幅 50% -> 应放行
conn.execute("INSERT INTO projects (id, name, stars, status, last_commit_at) VALUES ('a/growth','g',150,'active', ?)", (iso(10),))
conn.execute("INSERT INTO analyses (project_id, analyzed_at, overall_score) VALUES ('a/growth', ?, 7)", (iso(10),))
conn.execute("INSERT INTO tasks (project_id, task_date, task_type, status) VALUES ('a/growth', '2026-01-01', 'incremental', 'done')")
conn.execute("INSERT INTO star_history (project_id, sampled_at, stars) VALUES ('a/growth', date('now','-7 days'), 100)")
# 案例B：active、10 天前分析、无涨幅但昨天有 commit -> 应放行
conn.execute("INSERT INTO projects (id, name, stars, status, last_commit_at) VALUES ('a/commit','c',100,'active', ?)", (iso(1),))
conn.execute("INSERT INTO analyses (project_id, analyzed_at, overall_score) VALUES ('a/commit', ?, 7)", (iso(10),))
conn.execute("INSERT INTO tasks (project_id, task_date, task_type, status) VALUES ('a/commit', '2026-01-01', 'incremental', 'done')")
conn.execute("INSERT INTO star_history (project_id, sampled_at, stars) VALUES ('a/commit', date('now','-7 days'), 100)")
# 案例C：active、10 天前分析、无涨幅无新 commit -> 应抑制
conn.execute("INSERT INTO projects (id, name, stars, status, last_commit_at) VALUES ('a/quiet','q',100,'active', ?)", (iso(10),))
conn.execute("INSERT INTO analyses (project_id, analyzed_at, overall_score) VALUES ('a/quiet', ?, 7)", (iso(10),))
conn.execute("INSERT INTO tasks (project_id, task_date, task_type, status) VALUES ('a/quiet', '2026-01-01', 'incremental', 'done')")
conn.execute("INSERT INTO star_history (project_id, sampled_at, stars) VALUES ('a/quiet', date('now','-7 days'), 100)")
conn.commit(); conn.close()
sch = Scheduler(db.db_path, {'incremental': {'star_change_threshold': 0.05, 'recent_commit_days': 3, 'min_reanalyze_days': 7}})
n = sch.generate_incremental_tasks('2099-01-01', 10)
assert n == 2, f'expected 2 tasks, got {n}'
conn = db.get_conn()
ids = {r['project_id'] for r in conn.execute("SELECT project_id FROM tasks").fetchall()}
assert ids == {'a/growth', 'a/commit'}, ids
print('trigger rules OK:', ids)
EOF
```

Expected: 输出 `trigger rules OK: {'a/growth', 'a/commit'}`

- [ ] **Step 5: Commit**

```bash
git add framework/core/scheduler.py
git commit -m "feat: incremental scheduling uses cooldown + change trigger instead of daily re-analysis"
```

