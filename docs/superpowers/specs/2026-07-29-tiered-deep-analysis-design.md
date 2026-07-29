# 分层深读框架（L1 结构判读 + L2 证据化分析 + 评分反哺）— 设计文档

日期：2026-07-29
状态：已批准（三段设计逐段确认）
来源：2026-07-29 "创新分析限于 README" 设计讨论

## 1. 背景与目标

上一轮修复后，框架的创新分析输入只有 README + 元数据 + star 轨迹。README 是项目的自我陈述而非证据：判断不了声称是否成立、方案是否真新、痛点是否真实。

本 spec 引入**漏斗式分级深读**：L1 结构判读（不用 LLM 的确定性骨架事实提取）→ L2 证据化 LLM 分析（每条论断必须挂证据）→ L1 素材反哺评分信号（buzz/activity 从伪信号变真信号）。一份采集成本，分析与评分两处收益。

三个子判断与证据来源的对应关系：

1. "技术方案是否真新" → 核心源码文件 + 依赖清单（wrapper 判定）
2. "痛点是否真实" → issues 统计与标题
3. "与同类差异是否成立" → 现有 peers 机制 + LLM 先验（浅对比，不加深）

## 2. L1 结构判读

### 2.1 采集时机与预算

- 挂载点：discover 评分阶段（与 contributors 实采同位置）；analyze 阶段只读库存结果
- 触发：`projects.structure_json IS NULL` 或其中 `fetched_at` 超过 7 天（慢变素材，周期刷新）
- 预算：每日上限 `sources.github.structure_max_per_day`（默认 50），存量 ~250 个 scheduled/active 项目约 1 周补完；未补齐项目评分走现有 fallback，不阻塞

### 2.2 采集内容（约 2 次 API 调用/项目 + raw 免费抓取）

| 素材 | 调用 | 提取的骨架事实 |
|---|---|---|
| `GET /repos/{}/git/trees/HEAD?recursive=1` | 1 次 API | `has_tests` / `has_ci` / `has_docs` / `has_examples`（目录名匹配）；清单文件路径（pyproject.toml / package.json / Cargo.toml / go.mod，按项目语言取第一个命中）；`core_paths`（`src/`、`core/`、`lib/` 下路径含 model / inference / engine / agent / server 关键词的 .py/.ts/.rs/.go 文件，取前 3 个） |
| 清单文件内容 | raw.githubusercontent.com（不占 API 限额） | `dependencies` 列表；`is_wrapper_likely`：依赖与 `filters.known_ecosystem_packages`（config 新增键）有交集 |
| `GET /repos/{}/issues?state=all&sort=comments&direction=desc&per_page=10` | 1 次 API | `issue_health`：top10 reaction 总和、平均评论数、近 30 天活跃 issue 数（top10 中 `updated_at` 在近 30 天内的条数）；另存 `top_issues`：评论数前 5 的 `{title, comments, reactions}`（供 L2 直接使用，避免重复调用） |

### 2.3 存储

- `projects` 表加列 `structure_json TEXT`（`_add_column_if_missing` 软迁移）
- 结构：`{"fetched_at", "has_tests", "has_ci", "has_docs", "has_examples", "dependencies", "is_wrapper_likely", "core_paths", "issue_health": {...}}`
- 降级：子项失败互不影响；整体失败 → 留 NULL，下次预算内重试

### 2.4 独立性

L1 不碰 LLM、不改 prompt、不改评分公式，单独交付即有价值。

## 3. L2 证据化 LLM 分析

### 3.1 输入组装（analyze.py）

`get_project_data` 在现有 README 抓取基础上增加：

1. **骨架事实**：读 `projects.structure_json`（0 成本）
2. **核心文件节选**：按 `core_paths` 取前 3 个文件，经 `raw.githubusercontent.com/{repo}/HEAD/{path}` 抓取（不占 API 限额），各取前 5000 字符；core_paths 为空或抓取失败 → 该段标注 unavailable，分析继续
3. **社区信号**：`issue_health` 统计 + `top_issues` 标题列表（均来自 `structure_json`，0 成本）

### 3.2 prompt 契约（ai_analyze.md）

新增三个输入段（骨架事实 / 核心实现节选 / 社区信号）。README 段保留但降级为背景材料。

输出 schema 新增四个字段：

```
innovation_evidence: string[]  — 每条创新论断引用具体证据（文件名+机制描述），只允许来自核心实现节选或骨架事实
problem_evidence:    string[]  — 痛点论断引用 issue 标题/数据
confidence:          "high" | "medium" | "low"
cannot_determine:    string[]  — 材料不足以判断的维度名
```

证据约束指令（写入 prompt）：**创新性结论只能基于核心实现节选，不得基于 README 的宣称；痛点结论只能基于社区信号；没有证据的维度必须填入 cannot_determine，禁止编造。**

### 3.3 校验与存储

- `validate_analysis_output` 新增校验：`innovation_evidence` / `problem_evidence` / `cannot_determine` 必须是 list（非 list 归一化为 []）；`confidence` 必须枚举值（非法归一为 'medium'）
- `analyses` 表加列 `evidence_json TEXT`（`_add_column_if_missing` 软迁移，与 `projects.structure_json` 同批）：LLM 路径存四个字段的 JSON；heuristic 路径存 NULL
- heuristic 路径不变（仅分类职能），prompt 契约只约束 LLM 路径

### 3.4 报告

Top Opportunities 区不变；early-burst 项目区不加新展示（YAGNI）。`evidence_json` 供查询/审计，并作为后续"分析质量闭环"的数据基础。

## 4. 评分反哺

### 4.1 community_buzz 复活为真信号

- `ScoringEngine` 新增 `calculate_buzz(issue_health: Optional[Dict]) -> float`：
  - 打分依据（阈值 config 化，`early_burst.metrics.community_buzz.thresholds`）：top10 reaction 总和（主）、近 30 天活跃 issue 数（辅）、平均评论数（辅）
  - `issue_health` 为 None（L1 未覆盖）→ 走现有 `default_buzz_score()` 常量 fallback，行为与今天一致
- `config.yaml` 权重重排：`star_velocity 0.40` / `activity_index 0.30` / `novelty_signal 0.20` / `community_buzz 0.10`（buzz 小权重复活，真实价值交由 reweight 闭环用数据校准）
- `reweight.py` 的 `COMPONENTS` 加回 `community_buzz`（`backtest` 已是组件驱动，天然兼容）；`prediction_outcomes.community_buzz_at_pred` 恢复写入实值

### 4.2 activity_index 增强

- `calculate_activity_index(open_issues, commit_frequency, pr_merge_rate=None, has_tests=None, has_ci=None)`：新增两个可选参数，默认 None 时行为与现状完全一致
- L1 有数据时：`has_tests` 且 `has_ci` → 现有得分 +0.1（上限 1.0）；缺一 → +0.05
- discover 评分处从 `structure_json` 读取传入；无 L1 数据不传，走原路径

## 5. 成本明账（稳态每天）

| 项 | 计算 | 调用数 |
|---|---|---|
| L1 结构判读 | ≤50 预算 × ~2 次 API（清单文件走 raw 免费） | ≤100 |
| L2 核心文件 + 社区信号 | 核心文件走 raw 免费；社区信号读 structure_json | ≈0 |
| 现有开销（前 spec §2.5） | topics / ecosystem / trending / backfill / commits / README | ~400-500 |
| **合计** | | **~500-600**，限额内宽裕 |

## 6. 数据库变更

仅两列软迁移（`_add_column_if_missing`，框架已有机制，无需重建表）：

- `projects.structure_json TEXT`
- `analyses.evidence_json TEXT`

## 7. 验证方式

沿用"直接运行验证"惯例，无测试框架：

1. L1 正确性：对 3 个已知项目（有 tests/CI 的、明显 wrapper 的、从零实现的）核对 structure_json 各字段
2. L1 幂等：当天二次运行不重复采集（fetched_at 新鲜）
3. L2：`--use-llm --max-tasks 1` 真实分析，检查 evidence_json 四字段齐全、evidence 引用真实文件/issue、无证据维度进 cannot_determine
4. 反哺：L1 覆盖前后对同一项目算分，确认 buzz 从常量变为实值、activity 加分生效、无 L1 数据项目得分不变
5. `reweight.py --dry-run` 在 4 组件下不崩；`validate.py --metrics-only` 正常
6. 全链路：手动各阶段跑一遍（不 push），确认日调用量符合 §5 预算

## 8. 明确不做（YAGNI）

- 不做 L3 agent 深潜（保留为人工操作，不写代码）
- 不改 Top Opportunities 报告结构
- issues 正文级分析（只到标题 + 统计层）
- 刷新策略差异化（7 天固定周期）
- 深度同类对比（维持现有浅 peers 机制）

## 9. 已知限制

1. raw.githubusercontent.com 不经 API 但受 GitHub 页面层限流影响，大批量抓取可能 429 —— 每日 ≤45 个文件（15 项目 × 3），风险低
2. `is_wrapper_likely` 依赖 config 的生态包名单，名单外的 wrapper 会漏判（方向保守：漏判只影响该布尔值，不阻塞分析）
3. issue 信号对"新而爆"的项目天然稀薄（还没积累 issue）—— buzz 打低分方向保守，可接受

