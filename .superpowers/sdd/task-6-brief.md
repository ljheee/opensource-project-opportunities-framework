### Task 6: reweight.py 移除 buzz 组件并修复 backtest

**Files:**
- Modify: `framework/stages/reweight.py:20-26`（COMPONENTS/COMPONENT_COLS）
- Modify: `framework/stages/reweight.py:224-244`（`backtest`）

**Interfaces:**
- Consumes: config.yaml 新权重（Task 1）
- Produces: 无新接口；`python framework/stages/reweight.py --dry-run` 在 3 组件下不崩

- [ ] **Step 1: 写失败验证**

```bash
PYTHONPATH=. python3 -c "
import framework.stages.reweight as rw
assert 'community_buzz' not in rw.COMPONENTS, 'buzz still in COMPONENTS'
rows = [
  {'star_velocity_at_pred':0.8,'activity_index_at_pred':0.7,'community_buzz_at_pred':0.3,'novelty_at_pred':0.5,'outcome':'true_positive'},
  {'star_velocity_at_pred':0.4,'activity_index_at_pred':0.3,'community_buzz_at_pred':0.3,'novelty_at_pred':0.4,'outcome':'false_positive'},
]
w = {'star_velocity':0.45,'activity_index':0.35,'novelty_signal':0.20}
p, tp, fp = rw.backtest(rows, w, 0.5)
print('backtest OK:', p, tp, fp)
"
```

Expected: FAIL — 当前 `COMPONENTS` 含 `community_buzz`，且 `backtest` 访问 `new_weights['community_buzz']` 会 `KeyError`

- [ ] **Step 2: 修改 COMPONENTS / COMPONENT_COLS**

reweight.py:20-26 改为：

```python
COMPONENTS = ['star_velocity', 'activity_index', 'novelty_signal']
COMPONENT_COLS = {
    'star_velocity': 'star_velocity_at_pred',
    'activity_index': 'activity_index_at_pred',
    'novelty_signal': 'novelty_at_pred',
}
```

- [ ] **Step 3: `backtest` 改为按组件动态计算**

reweight.py:224-244 的 `backtest` 函数体重写为：

```python
def backtest(rows, new_weights, new_min_score):
    """Re-score historical predictions with new weights and threshold."""
    tp_new = 0
    fp_new = 0
    for r in rows:
        new_score = sum(
            (r.get(COMPONENT_COLS[c]) or 0) * new_weights.get(c, 0)
            for c in COMPONENTS
        )
        predicted_burst = new_score >= new_min_score
        actual_positive = r['outcome'] == 'true_positive'
        if predicted_burst and actual_positive:
            tp_new += 1
        elif predicted_burst and not actual_positive:
            fp_new += 1

    total_new = tp_new + fp_new
    precision_new = tp_new / total_new if total_new > 0 else 0.0
    return precision_new, tp_new, fp_new
```

- [ ] **Step 4: 重跑 Step 1 验证 + dry-run 冒烟**

```bash
python3 framework/stages/reweight.py --dry-run
```

Expected: Step 1 输出 `backtest OK`；dry-run 输出 `Insufficient data for weight adjustment`（当前 0 行 outcomes，正常路径不崩）

- [ ] **Step 5: Commit**

```bash
git add framework/stages/reweight.py
git commit -m "fix: drop community_buzz from reweight components, make backtest component-driven"
```

