# Design v2: Validation Loop & Product Differentiation

## 背景

当前框架已完成三轮代码审查修复和第一轮功能增强（acceleration scoring）。数据层面：

- 712 个项目（topic 395 + ecosystem 239 + trending 78）
- 50 个已过滤进入 active/scheduled 状态
- **0 个 early-burst**（因为首次运行，无 star history 基线）
- 10 条 LLM 分析记录

核心问题：**用户凭什么相信系统的判断？** 以及 **用户为什么不自己用 ChatGPT？**

---

## 第一部分：验证闭环（Validation Loop）

### 1.1 为什么必须做

当前系统的 scoring 权重（0.35/0.25/0.25/0.15）是拍脑袋定的。没有验证：
- 我们不知道标记为 early-burst 的项目后来真的爆发了吗
- 我们不知道哪些特征对预测真正有用
- 用户看到一个"early-burst"标签，没有任何理由信任它

### 1.2 方案设计

**核心数据流：**

```
预测（Predict） → 等待（Wait 7d+） → 验证（Validate） → 学习（Learn） → 调整（Adjust）
```

**预测阶段（已存在）：**
- `early_burst_signals` 表记录每个项目的评分和 `is_early_burst` 标记
- 首次 `is_early_burst=1` 时，`validate.py` 在 `prediction_outcomes` 表中创建一条 `pending` 记录

**等待阶段：**
- 预测后至少 7 天才能评估（让 star 增长有足够时间显现）
- 期间项目继续被采样，star_history 积累数据

**验证阶段（validate.py）：**
- 对 `pending` 且超过 7 天的记录：
  - 读取 `stars_at_prediction`（预测时的 star 数）
  - 读取当前 `projects.stars`（最新 star 数）
  - 计算实际日均增长率：`actual_growth = (stars_now - stars_then) / days`
  - 判定 outcome：
    - `true_positive`: 实际增长 >= 预期增长的 50%（预期增长 = overall_score * 8）
    - `false_positive`: 实际增长 < 预期增长的 50%

**学习阶段（四层递进，每层回答不同的问题）：**

为什么需要四层？因为只看一个 overall precision 只能告诉你"系统整体准不准"，但无法告诉你"为什么不准"以及"该优化哪里"。四层像体检：先量体温，再查血常规，再查具体器官，最后开药。

**第一层：Overall Precision（系统整体可信吗？）**

```
precision = TP / (TP + FP)
```

这是给用户看的"信心指标"。如果 precision = 60%，意味着每 10 个被标记为 early-burst 的项目，有 6 个确实在后续 7 天内加速了。用户看到这个数字，才有理由信任系统的判断。

**为什么不够？** precision = 60% 可能是"所有分数段都 60%"，也可能是"低分段 30%、高分段 90%"。这两种情况的天壤之别，overall precision 看不出来。

**第二层：Score Bucket Calibration（分数本身有意义吗？）**

把预测按 overall_score 分桶（0.65-0.7 / 0.7-0.8 / 0.8+），看各桶的实际 precision。

| 场景 A（理想） | 场景 B（灾难） |
|---------------|---------------|
| 0.8+ precision: 90% | 0.8+ precision: 40% |
| 0.7-0.8 precision: 70% | 0.7-0.8 precision: 75% |
| 0.65-0.7 precision: 50% | 0.65-0.7 precision: 55% |

场景 A：分数越高越准，模型在"说真话"。
场景 B：最高分桶反而最不准，模型在"虚高"——打分系统在 inflated scores，高分项目并没有真的更好。

**场景 B 的深层含义**：某个 component 可能在"作弊"。比如 community_buzz 默认给所有人 0.3，但如果某个项目的 buzz 因为随机因素被高估到 0.8，overall_score 会被虚高，但它并不真的在爆发。

**第三层：Component Correlation（哪个指标在起作用，哪个是废的？）**

对比 TP 和 FP 在四个 component 上的平均分：

```
                star_velocity  activity  community_buzz  novelty
TP 平均分:      0.72          0.65      0.31            0.58
FP 平均分:      0.45          0.62      0.29            0.61
差异:           +0.27         +0.03     +0.02           -0.03
```

这个结果告诉我们：**star_velocity 是唯一的有效信号**。TP 项目的 star_velocity 显著高于 FP，其他三个指标没有区分力。

**为什么要找这个？** 因为当前权重是 star_velocity 0.35 / activity 0.25 / buzz 0.25 / novelty 0.15。但实际上 activity、buzz、novelty 加起来占了 65% 的权重，却对预测对错几乎没有影响。这 65% 的权重是在"浪费算力"。

**第四层：Threshold Optimization（门槛设多高最合适？）**

当前 min_score = 0.65，这是拍脑袋的。通过历史数据扫描不同阈值：

| Threshold | Precision | 被保留的预测数 |
|-----------|-----------|--------------|
| 0.55      | 45%       | 100%         |
| 0.65      | 62%       | 68%          |
| 0.70      | 71%       | 45%          |
| 0.75      | 78%       | 28%          |

如果用户需要"宁可漏掉也不错杀"，保持 0.65。如果用户需要"宁杀错不放过"，提高到 0.75。

**为什么需要这层？** 因为 precision 和 coverage 是 trade-off。提高门槛 → precision 上升但 coverage 下降（漏掉更多项目）。没有历史数据，这个 trade-off 是盲猜的。

**调整阶段（未来迭代）：**

基于 Learn 阶段的四层输出，决定三件事：
1. **min_score 调多少** → 由 Threshold Optimization 决定
2. **哪个 component 降权** → 由 Component Correlation 决定
3. **降多少** → 保守渐进，单次不超过 ±20%，每月只调一次

最终目标：实现 `reweight.py --dry-run` 输出调整建议，人工确认后 `--apply` 生效。

### 1.3 报告输出

日报新增 **Validation Metrics** 区块：

```markdown
## Validation Metrics

- Predictions evaluated: 42 (TP: 28, FP: 14)
- Precision (7d+ horizon): 66.7%
- Avg actual growth — TP: 12.3 stars/day, FP: 1.8 stars/day

### Score Bucket Calibration
| Bucket | Evaluated | Precision |
|--------|-----------|-----------|
| 0.8+   | 8         | 87.5%     |
| 0.7-0.8| 15        | 73.3%     |
| 0.65-0.7| 19       | 52.6%     |
```

### 1.4 GitHub Actions 集成

在现有 workflow 中增加一个 weekly job：

```yaml
- name: Validate Predictions
  run: python framework/stages/validate.py
```

每天运行 `discover + filter + score`，每周运行一次 `validate`，每月运行一次 `reweight`（权重调整）。

---

## 第二部分：产品差异化——"为什么不是直接用 ChatGPT"

### 2.1 当前差距

| 能力 | 用户手动 + ChatGPT | 当前系统 |
|------|-------------------|----------|
| 静态项目信息 | 可以复制粘贴 | 自动获取 |
| Star 历史曲线 | 需要手动收集 | 已自动采样 |
| 同类项目对比 | 需要手动搜索 | **缺失** |
| 增长拐点检测 | 肉眼判断 | **缺失** |
| 持续追踪 | 无法每天手动查 | 自动定时运行 |
| 结构化报告 | 每次从零开始 | 自动生成 |

当前系统只解决了"静态信息获取"和"定时运行"，在**分析深度**上并没有超越 ChatGPT。

### 2.2 差异化方案：三层专有信号

#### 信号层 1：Temporal Trajectory（时间轨迹）✅ 已实现

- 30 天 star 历史表格，包含日增量和百分比变化
- 明确指令 LLM："不要只看当前 star 数，关注变化率的趋势和拐点"
- **ChatGPT 做不到**：因为它没有持续采集历史数据的能力

#### 信号层 2：Peer Radar（竞品雷达）⬜ 设计中

**核心洞察**：单个项目的绝对数字没有意义，relative positioning 才有意义。

**数据供给**：
- 对目标项目，找到同 `tech_layer` + `application` 的已过滤项目（最多 5 个）
- 提供每个 peer 的：name, stars, url
- 计算目标项目在 peer group 中的 percentile（star 数排名百分比）

**Prompt 中的呈现**：

```markdown
## Peer Comparison (Same Category: foundation_model / code_generation)

| Project | Stars | URL |
|---------|-------|-----|
| project-a | 350 | https://github.com/... |
| **THIS PROJECT** | **200** | https://github.com/... |
| project-c | 180 | https://github.com/... |

Percentile in peer group: 67% (above 2 of 3 peers)
```

**LLM 指令**："Use this peer data to assess relative competitive positioning. Is this project overperforming or underperforming vs. direct open-source competitors in the same space?"

**ChatGPT 做不到**：因为它不知道你的数据库里有哪些同类项目，也不知道它们的实时 star 数。

#### 信号层 3：Inflection Point Detection（拐点检测）⬜ 设计中

**核心洞察**：项目的 star 曲线不是直线，关键问题是"现在处于什么阶段"。

**算法**：
1. 计算相邻采样点的斜率（stars/day）
2. 比较最近两段斜率：
   - `slope_recent` = (latest - mid) / days
   - `slope_prior` = (mid - earliest) / days
3. 判定阶段：
   - `slope_recent > slope_prior * 1.5` → "accelerating"（加速期）
   - `slope_recent > slope_prior * 0.8` → "stable_growth"（稳定增长期）
   - `slope_recent < slope_prior * 0.5` → "decelerating"（减速期）
   - `slope_recent < 0` → "decline"（衰退期）

**Prompt 中的呈现**：

```markdown
## Inflection Point Analysis

- Phase: accelerating
- Recent slope: 8.5 stars/day
- Prior slope: 3.2 stars/day
- Assessment: Growth rate has more than doubled in the past week. This suggests a recent catalyst (viral post, feature release, or community endorsement).
```

**ChatGPT 做不到**：因为它没有持续的时间序列数据，也无法做简单的斜率比较。

### 2.3 差异化总结

当用户问"为什么我不自己用 ChatGPT"时，答案应该是：

> "你可以把项目描述粘贴给 ChatGPT，得到一份基于静态信息的分析。但 ChatGPT 不知道：
> 1. 这个项目过去 30 天的 star 增长曲线是加速还是减速
> 2. 它在同类开源项目中排第几 percentile
> 3. 它最近是否出现了一个增长拐点（比如从 3 stars/day 跳到 8 stars/day）
> 
> 这三层信号需要持续的数据采集和结构化对比，ChatGPT 做不到，而系统每天都在自动做。"

---

## 第三部分：实施优先级

| 优先级 | 功能 | 状态 | 说明 |
|--------|------|------|------|
| P0 | Acceleration scoring | ✅ 已落地 | 本周 star 增长斜率是前 2 周的几倍 |
| P0 | Validation table + script | ✅ 已落地 | prediction_outcomes + validate.py |
| P0 | Peer Radar | ⬜ **待实现** | 同类别竞品对比（差异化核心） |
| P1 | Trajectory in LLM prompt | ✅ 已落地 | Star history 表格加入 prompt |
| P1 | Inflection Point Detection | ⬜ **待实现** | 斜率变化检测 + 阶段判定 |
| P1 | Report validation metrics | ⚠️ 基础版 | 需要细化 score bucket calibration |
| P2 | Weight auto-tuning | ⬜ 待实现 | 基于 validation 结果自动调权重 |

---

## 第四部分：数据预期时间线

| 天数 | 预期现象 |
|------|----------|
| Day 1（今天） | 712 个项目入库，0 early-burst（无 history 基线） |
| Day 3 | Star history 有 3 个采样点，部分项目可计算 7d 速度 |
| Day 7 | Star history 足够，首批 early-burst 项目浮出水面 |
| Day 14 | 7 天前的预测进入可验证状态，validate.py 产出首批 precision |
| Day 21 | Acceleration scoring（14d/21d）完全生效，模型区分度达到最佳 |
| Day 30 | 有足够数据做 weight calibration，可考虑启动 auto-tuning |

**关键认知**：今天看不到 early-burst 是**预期内**的，不是 bug。需要耐心等待 7–14 天的数据积累。
