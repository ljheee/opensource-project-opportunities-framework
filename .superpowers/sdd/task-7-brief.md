### Task 7: validate.py 召回率回溯（FN 算法）

**Files:**
- Modify: `framework/stages/validate.py`（`record_new_predictions`、`check_pending_outcomes`、`print_metrics`）

**Interfaces:**
- Consumes: `early_burst_signals.is_early_burst`、`projects.source`、`star_history` 最早样本
- Produces: `prediction_outcomes.outcome` 新值 `false_negative` / `true_negative`；方向区分规则：`overall_score_at_prediction >= min_score` 为 TP 候选，否则为 FN 候选
- 固定 FN 阈值 = `min_score × 8 × 0.5`（当前 0.65×8×0.5 = 2.6 stars/day），与 `_predicted_growth` 同源

- [ ] **Step 1: 顶部加配置读取与阈值常量**

validate.py 的 import 区（第 14 行 `from framework.core.db import Database` 后）追加：

```python
from datetime import datetime, timezone

from framework.core.config_loader import ConfigLoader


def _fn_threshold() -> float:
    """Fixed false-negative threshold: min_score x 8 x 0.5 (same basis as TP rule)."""
    try:
        min_score = ConfigLoader().get_early_burst_config().min_score
    except Exception:
        min_score = 0.65
    return min_score * 8 * 0.5
```

注意：**方向判定不读 min_score**——FN 候选行在记录时组件列全 NULL，check 时用 `star_velocity_at_pred IS NULL` 判方向（见 Step 3），这样 reweight 未来调整 min_score 不会重分类存量 pending 行。

- [ ] **Step 2: `record_new_predictions` 增加 FN 候选记录**

现有函数（validate.py:27-75）末尾 `conn.commit()` **之前**插入 FN 候选段：

```python
        # FN candidates: trending-source projects that did NOT reach early-burst,
        # old enough to evaluate, and never recorded before.
        fn_threshold = _fn_threshold()
        fn_cur = conn.execute('''
            SELECT p.id as project_id, p.first_seen_at, p.stars,
                   e.overall_score, e.calculated_at
            FROM projects p
            JOIN (
                SELECT project_id, overall_score, calculated_at,
                       ROW_NUMBER() OVER (PARTITION BY project_id ORDER BY calculated_at DESC) as rn
                FROM early_burst_signals
            ) e ON p.id = e.project_id AND e.rn = 1
            WHERE p.source = 'trending'
              AND e.is_early_burst IS NOT 1
              AND julianday('now') - julianday(p.first_seen_at) >= ?
              AND NOT EXISTS (
                  SELECT 1 FROM prediction_outcomes po WHERE po.project_id = p.id
              )
        ''', (min_days_for_fn,))

        fn_recorded = 0
        for row in fn_cur.fetchall():
            baseline = conn.execute('''
                SELECT stars FROM star_history
                WHERE project_id = ? ORDER BY sampled_at ASC LIMIT 1
            ''', (row['project_id'],)).fetchone()
            baseline_stars = baseline['stars'] if baseline else row['stars']
            # 无星史样本时基线是当前 stars，checked_at 记首次发现日（spec §2.4-2）
            if baseline:
                checked_at = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            else:
                checked_at = str(row['first_seen_at'])[:10]
            conn.execute('''
                INSERT INTO prediction_outcomes
                (project_id, predicted_at, stars_at_prediction,
                 overall_score_at_prediction,
                 star_velocity_at_pred, activity_index_at_pred,
                 community_buzz_at_pred, novelty_at_pred,
                 growth_rate_predicted,
                 checked_at, outcome)
                VALUES (?, ?, ?, ?, NULL, NULL, NULL, NULL, ?, ?, 'pending')
            ''', (row['project_id'], row['first_seen_at'],
                  baseline_stars, row['overall_score'],
                  fn_threshold, checked_at))
            fn_recorded += 1
        print(f"Recorded {fn_recorded} new FN candidates")
```

注意 `e.is_early_burst IS NOT 1` 匹配 0 和 NULL（SQLite `IS NOT` 语义）。且该查询引用了 `e.is_early_burst`，需把它加入子查询 SELECT 列表：

```python
                SELECT project_id, overall_score, calculated_at, is_early_burst,
                       ROW_NUMBER() OVER (PARTITION BY project_id ORDER BY calculated_at DESC) as rn
```

`record_new_predictions` 签名加参数：`def record_new_predictions(db: Database, min_days_for_fn: int = 7):`

- [ ] **Step 3: `check_pending_outcomes` 加方向分支**

先给现有 SELECT（validate.py:83-93）加一列——方向判定需要它：

```sql
            SELECT po.id, po.project_id, po.stars_at_prediction,
                   po.overall_score_at_prediction, po.predicted_at,
                   po.growth_rate_predicted, po.star_velocity_at_pred,
                   p.stars as stars_now,
```

然后 validate.py:96-141 的行内处理循环中，把判定段（现有 124-130 行的 TP/FP 判定）替换为：

```python
            # 方向在记录时已固化：FN 候选行的组件列全为 NULL（Step 2 插入的）。
            # 不要用 score vs 当前 min_score 重判——reweight 可能已调整阈值，
            # 会把存量 TP 候选行错误重分类。
            is_tp_candidate = row['star_velocity_at_pred'] is not None

            if is_tp_candidate:
                # 原有 TP 候选逻辑（保持不变）
                if stars_now <= stars_then:
                    outcome = 'false_positive'
                elif actual_growth >= predicted_growth * 0.5:
                    outcome = 'true_positive'
                else:
                    outcome = 'false_positive'
            else:
                # FN 候选：实际增速超过固定阈值 = 我们漏掉的爆发
                if actual_growth >= _fn_threshold():
                    outcome = 'false_negative'
                else:
                    outcome = 'true_negative'
```

（`predicted_growth` 变量在 FN 分支未用，但 UPDATE 仍写回，保持现有 UPDATE 语句不变。）

- [ ] **Step 4: `print_metrics` 加 FN/TN 与 recall**

validate.py:152-177 的计数区，在 `pending` 计数后追加：

```python
        try:
            fn = int(conn.execute(
                "SELECT COUNT(*) FROM prediction_outcomes WHERE outcome = 'false_negative'"
            ).fetchone()[0] or 0)
        except (ValueError, TypeError):
            fn = 0
        try:
            tn = int(conn.execute(
                "SELECT COUNT(*) FROM prediction_outcomes WHERE outcome = 'true_negative'"
            ).fetchone()[0] or 0)
        except (ValueError, TypeError):
            tn = 0
```

在 `print(f"Precision (7d+ horizon): ...")` 块后追加：

```python
        print(f"Recall candidates — FN (missed bursts): {fn}, TN: {tn}")
        if tp + fn > 0:
            print(f"Recall (trending-source): {tp / (tp + fn):.2%}")
```

- [ ] **Step 5: 构造数据验证（spec §4 验证项 7 的 FN 构造用例）**

```bash
PYTHONPATH=. python3 - <<'EOF'
from framework.core.db import Database
db = Database('/tmp/fn_test.db')
db.init_tables()
conn = db.get_conn()
# 造一个 trending 源、未达标、10 天前首次发现、当时 100 stars、现在 500 stars 的项目
conn.execute("""INSERT INTO projects (id, name, url, stars, source, status, first_seen_at)
  VALUES ('a/b', 'b', 'http://x', 500, 'trending', 'discovered', datetime('now', '-10 days'))""")
conn.execute("INSERT INTO star_history (project_id, sampled_at, stars) VALUES ('a/b', date('now','-10 days'), 100)")
conn.execute("INSERT INTO early_burst_signals (project_id, calculated_at, overall_score, is_early_burst) VALUES ('a/b', datetime('now','-10 days'), 0.40, 0)")
conn.commit(); conn.close()

import framework.stages.validate as v
v.record_new_predictions(db, min_days_for_fn=7)
v.check_pending_outcomes(db, min_days=7)
conn = db.get_conn()
row = conn.execute("SELECT * FROM prediction_outcomes WHERE project_id='a/b'").fetchone()
d = dict(row); print(d)
# 增速 = (500-100)/10 = 40 stars/day >= 2.6 -> false_negative
assert d['outcome'] == 'false_negative', d['outcome']
conn.close()
print('FN pipeline OK')
EOF
```

Expected: 输出 `FN pipeline OK`（若断言行顺序因日期边界差 1 天失败，把 -10 改为 -12 重跑）

- [ ] **Step 6: Commit**

```bash
git add framework/stages/validate.py
git commit -m "feat: track false negatives for trending-source misses (recall loop)"
```

