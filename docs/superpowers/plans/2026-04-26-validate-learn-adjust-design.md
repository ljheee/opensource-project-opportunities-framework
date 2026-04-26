# Design: Validate → Learn → Adjust 闭环详解

## 核心问题

当前系统的 scoring 权重是拍脑袋定的：

```yaml
star_velocity: 0.35
activity_index: 0.25
community_buzz: 0.25
novelty_signal: 0.15
```

凭什么 star_velocity 占 35%？凭什么不是 40% 或 20%？没有人知道。

Validate → Learn → Adjust 闭环的目标是：**让系统用数据回答这个问题**，而不是靠直觉。

---

## 一、Validate（验证）：预测准不准？

### 1.1 预测记录

当 `scoring_engine.calculate_overall()` 判定 `is_early_burst = 1` 时，系统立即在 `prediction_outcomes` 表中记录：

```sql
INSERT INTO prediction_outcomes (
    project_id, predicted_at,
    stars_at_prediction, overall_score_at_prediction,
    star_velocity_at_pred, activity_index_at_pred,
    community_buzz_at_pred, novelty_at_pred,
    outcome
) VALUES (...)
```

**关键设计**：不仅记录 overall_score，还要记录**每个 component 的原始分数**。这是 Learn 阶段的基础数据。

### 1.2 等待期

预测后不能立即判定对错。 star 增长需要时间来显现。设置 **最小验证窗口 7 天**：

- 7 天内：outcome = 'pending'
- 7 天后：允许 validate.py 进行评估

为什么是 7 天？因为系统的核心检测周期就是 7 天（past_7d）。一个项目的 7 天增长趋势，需要至少 7 天后才能验证。

### 1.3 评估标准

**核心原则**：不看绝对 star 数，看**相对增长**。

假设预测时项目有 100 stars，overall_score = 0.70。7 天后实际增长到 120 stars。

- 绝对增长：+20 stars
- 实际日均增长：20 / 7 = 2.86 stars/day

**预期增长模型**：

```
predicted_daily_growth = overall_score * 8   # 经验系数
# 0.70 * 8 = 5.6 stars/day expected
```

系数 8 的来源：假设一个项目的 overall_score = 1.0（满分），预期它每天增长 8 stars（这在 AI 开源项目中属于高活跃水平）。这是一个经验常数，后续可以通过 Learn 阶段优化。

**判定逻辑**：

```python
if actual_growth >= predicted_growth * 0.5:
    outcome = 'true_positive'   # 至少达到了预期的一半
else:
    outcome = 'false_positive'  # 增长不及预期
```

为什么是 0.5（50%）而不是 100%？
- 预测本身就是有噪声的
- 开源项目的 star 增长受很多外部因素影响（HN 热帖、名人 tweet）
- 50% 是一个合理的"及格线"：项目确实在增长，虽然没有模型预期的那么快

**反例处理**：
- 如果 stars_now < stars_then（star 数下降），直接判 FP
- 如果 stars_now == stars_then（零增长），直接判 FP

### 1.4 Validate.py 运行时机

不是每次 Actions 都运行。而是：

```yaml
# GitHub Actions workflow
jobs:
  daily_pipeline:
    runs-on: ubuntu-latest
    steps:
      - run: python framework/stages/discover.py
      - run: python framework/stages/filter.py
      - run: python framework/stages/schedule.py
      # 只在每周一运行验证
      - run: python framework/stages/validate.py
        if: github.event.schedule == '0 6 * * 1'
```

**为什么不是每天？**
- 每天运行的话，大部分 pending 预测还没到 7 天，无法评估
- 每周一次足够：积累一周的成熟预测，批量评估
- 减少 API 调用和计算开销

---

## 二、Learn（学习）：从对错中提取规律

### 2.1 第一层：Overall Precision

最基础的指标：

```
precision = TP / (TP + FP)
```

如果 precision < 50%，说明系统在"瞎猜"，比抛硬币还糟。

如果 precision > 70%，说明模型有实用价值。

**目标 precision：> 60%**（作为早期系统，60% 是可以接受的起点）。

### 2.2 第二层：Score Bucket Calibration（分数桶校准）

把预测按 overall_score 分桶，看各桶的实际 precision：

```sql
SELECT
    CASE
        WHEN overall_score_at_prediction >= 0.85 THEN '0.85+'
        WHEN overall_score_at_prediction >= 0.75 THEN '0.75-0.85'
        WHEN overall_score_at_prediction >= 0.65 THEN '0.65-0.75'
        ELSE '<0.65'
    END as bucket,
    COUNT(*) as total,
    SUM(CASE WHEN outcome = 'true_positive' THEN 1 ELSE 0 END) as tp
FROM prediction_outcomes
WHERE outcome != 'pending'
GROUP BY bucket
```

**理想状态**：分数桶越高，precision 越高（单调递增）。

**如果现实不是这样**，比如：

| Bucket | Total | Precision |
|--------|-------|-----------|
| 0.85+  | 5     | 40%       |
| 0.75-0.85 | 12 | 75%       |
| 0.65-0.75 | 20 | 55%       |

这说明 **0.85+ 桶的模型过度自信了**。高分项目反而更可能出错，模型在"膨胀"。

### 2.3 第三层：Component Correlation（特征相关性）

这是 Learn 阶段的核心。回答：**哪个 component 对预测对错的影响最大？**

对每个 prediction_outcome 记录，计算：

```python
# 给 TP 和 FP 分别统计 component 分数分布
tp_records = [r for r in outcomes if r['outcome'] == 'true_positive']
fp_records = [r for r in outcomes if r['outcome'] == 'false_positive']

for component in ['star_velocity', 'activity_index', 'community_buzz', 'novelty']:
    tp_avg = avg(r[f'{component}_at_pred'] for r in tp_records)
    fp_avg = avg(r[f'{component}_at_pred'] for r in fp_records)
    
    # 如果 TP 的 component 分数显著高于 FP，说明这个 component 有区分力
    discriminative_power = tp_avg - fp_avg
```

**三种可能的结果**：

1. **star_velocity 区分力最强**（tp_avg >> fp_avg）
   - 说明 star 增长趋势是可靠的早期信号
   - 结论：保持或提高 star_velocity 权重

2. **community_buzz 区分力最弱**（tp_avg ≈ fp_avg）
   - 说明 buzz score 没有预测价值（可能是因为数据缺失，默认 0.3 对所有人都一样）
   - 结论：降低 community_buzz 权重，或尝试引入更多 buzz 数据源

3. **novelty 区分力为负**（tp_avg < fp_avg）
   - 说明"越新的项目越容易 burst"这个假设是错的
   - 结论：降低 novelty 权重，或重新审视 novelty 的计算方式

### 2.4 第四层：Threshold Optimization（阈值优化）

当前 `min_score = 0.65`。这是 early-burst 的门槛。

但 0.65 是最佳选择吗？通过历史数据可以计算不同阈值下的 precision：

```python
for threshold in [0.55, 0.60, 0.65, 0.70, 0.75, 0.80]:
    subset = [r for r in outcomes if r['overall_score_at_prediction'] >= threshold]
    tp = sum(1 for r in subset if r['outcome'] == 'true_positive')
    fp = sum(1 for r in subset if r['outcome'] == 'false_positive')
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    coverage = len(subset) / len(outcomes)  # 有多少预测被保留
    print(f"Threshold {threshold}: precision={precision:.2%}, coverage={coverage:.1%}")
```

**输出示例**：

| Threshold | Precision | Coverage |
|-----------|-----------|----------|
| 0.55      | 45%       | 100%     |
| 0.65      | 62%       | 68%      |
| 0.70      | 71%       | 45%      |
| 0.75      | 78%       | 28%      |
| 0.80      | 85%       | 12%      |

**决策**：如果用户需要"宁可漏掉也不错杀"（高 recall），保持 0.65。如果用户需要"宁杀错不放过"（高 precision），提高到 0.75。

**系统默认值**：选择 precision 首次突破 65% 的最小阈值。上例中是 0.65（刚好 62%，接近）。

---

## 三、Adjust（调整）：把学习结果应用到系统

### 3.1 调整什么？

三个可调参数：

1. **min_score**（early-burst 阈值）
2. **component weights**（四个指标的权重）
3. **predicted_growth_coefficient**（预期增长系数，当前是 8）

### 3.2 调整策略：保守渐进

**绝对不做的**：每天大幅调整权重。这会导致系统"摇摆不定"，今天说 A 重要，明天说 B 重要。

**应该做的**：

```python
# 每月评估一次，每次调整幅度不超过 ±20%
ADJUSTMENT_INTERVAL_DAYS = 30
MAX_ADJUSTMENT_RATIO = 0.20

def adjust_weight(current_weight, target_weight):
    """Move current_weight toward target_weight, but cap the change."""
    max_change = current_weight * MAX_ADJUSTMENT_RATIO
    delta = target_weight - current_weight
    
    if abs(delta) > max_change:
        delta = max_change if delta > 0 else -max_change
    
    return current_weight + delta
```

**为什么保守？**
- 开源项目的 star 增长有很强的随机性（一次 HN 热帖可以让任何项目暴涨）
- 小样本下（每月可能只有 20-50 个可验证的预测），统计噪音很大
- 渐进调整让系统平稳进化，而不是剧烈震荡

### 3.3 权重调整的数学方法

**方法一：Correlation-based（基于相关性）**

```python
# 计算每个 component 与 outcome 的相关系数
from statistics import correlation

for component in components:
    scores = [r[f'{component}_at_pred'] for r in outcomes]
    labels = [1 if r['outcome'] == 'true_positive' else 0 for r in outcomes]
    corr = correlation(scores, labels)
    
    # corr 范围 [-1, 1]
    # corr > 0.3: 强正相关，提高权重
    # corr 0.1-0.3: 弱正相关，保持权重
    # corr < 0.1: 无相关，降低权重
```

**方法二：Logistic Regression（逻辑回归）**

```python
from sklearn.linear_model import LogisticRegression

X = [[r['star_velocity_at_pred'], r['activity_index_at_pred'],
      r['community_buzz_at_pred'], r['novelty_at_pred']]
     for r in outcomes]
y = [1 if r['outcome'] == 'true_positive' else 0 for r in outcomes]

model = LogisticRegression()
model.fit(X, y)

# model.coef_ 就是每个 feature 的权重
new_weights = normalize(model.coef_[0])
```

**推荐**：先用方法一（简单、可解释、不需要 sklearn 依赖），积累 100+ 验证样本后再考虑方法二。

### 3.4 调整后的验证

每次调整后，必须做**回测（backtest）**：

```python
# 用新权重重新计算历史项目的 overall_score
# 看如果用新权重，历史 precision 会提高还是降低

for record in outcomes:
    new_score = (
        record['star_velocity_at_pred'] * new_weights['star_velocity'] +
        record['activity_index_at_pred'] * new_weights['activity_index'] +
        record['community_buzz_at_pred'] * new_weights['community_buzz'] +
        record['novelty_at_pred'] * new_weights['novelty']
    )
    
    # 用新的 min_score 重新判定 is_early_burst
    new_outcome = 'true_positive' if new_score >= new_min_score and record['outcome'] == 'true_positive' else ...

# 如果回测 precision 下降，拒绝这次调整
```

**这是防止模型退化（model degradation）的最后一道防线。**

### 3.5 人工审核机制

自动调整不是完全无人监督的。设计一个"调整建议"模式：

```python
# reweight.py --dry-run
python framework/stages/reweight.py --dry-run
```

输出：

```
=== Weight Adjustment Proposal ===
Based on 47 validated predictions (TP: 28, FP: 19)

Current weights:
  star_velocity: 0.35
  activity_index: 0.25
  community_buzz: 0.25
  novelty: 0.15

Proposed weights:
  star_velocity: 0.38 (+8.6%)
  activity_index: 0.28 (+12.0%)
  community_buzz: 0.18 (-28.0%)  ⚠️ significant drop
  novelty: 0.16 (+6.7%)

Proposed min_score: 0.68 (current: 0.65)

Backtest result:
  Old precision: 62%
  New precision: 67%  (+5pp)
  Coverage change: -8% (fewer projects flagged)

Run with --apply to commit these changes.
```

**默认行为**：`--dry-run`，输出建议但不修改 config。
**应用调整**：需要显式 `--apply`，或者人工编辑 config.yaml。

---

## 四、完整闭环时序图

```
Day 1: 发现项目 A，overall_score = 0.72，is_early_burst = 1
       → prediction_outcomes 插入记录（outcome='pending'）

Day 1-7: 项目 A 继续被采样，star_history 积累

Day 8: validate.py 运行
       → 项目 A 的 pending 记录已满 7 天
       → 计算 actual_growth = (stars_now - stars_then) / 7
       → 判定 outcome（TP 或 FP）

Day 8-30: 更多项目进入验证状态，积累 20-50 条验证记录

Day 30: reweight.py --dry-run 运行
       → 计算各 component 的 discriminative_power
       → 计算 optimal min_score
       → 输出调整建议

[人工审核后]

Day 31: reweight.py --apply 运行
       → 更新 config.yaml 中的 weights 和 min_score
       → 系统开始使用新权重进行后续评分

[循环回到 Day 1]
```

---

## 五、风险控制

### 5.1 样本量不足

如果验证样本 < 20，拒绝调整。统计学上 20 个样本是勉强可用的下限。

```python
if len(outcomes) < 20:
    print("Insufficient data for weight adjustment (need >= 20, got {len(outcomes)})")
    return
```

### 5.2 权重失衡

调整后任何 component 的权重不能 < 5% 或 > 60%。避免模型过度依赖单一指标。

```python
for component, weight in new_weights.items():
    if weight < 0.05:
        weight = 0.05
    if weight > 0.60:
        weight = 0.60
```

### 5.3 权重归一化

调整后四个权重之和必须 = 1.0。

```python
total = sum(new_weights.values())
new_weights = {k: v / total for k, v in new_weights.items()}
```

### 5.4 版本回滚

每次调整前备份当前 config.yaml：

```python
import shutil
from datetime import datetime

backup_path = f"config.yaml.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
shutil.copy('config.yaml', backup_path)
```

如果调整后发现 precision 连续两周下降，人工回滚到上一个版本。

---

## 六、成功标准

| 指标 | 当前 | 3 个月目标 | 6 个月目标 |
|------|------|-----------|-----------|
| Validated predictions | 0 | 50+ | 150+ |
| Precision | N/A | 60% | 70% |
| Score bucket monotonicity | N/A | 基本单调 | 严格单调 |
| Component correlation clarity | N/A | 知道哪个最重要 | 知道各component的相对价值 |
| Weight adjustment frequency | N/A | 每月 1 次 | 每月 1 次 |

**最关键的认知**：这个闭环不是"让系统自动变聪明"，而是"让系统的决策有数据支撑"。即使 precision 只有 60%，用户也能看到"60% 的项目确实爆发了"，这比"我觉得这个项目会火"有说服力得多。
