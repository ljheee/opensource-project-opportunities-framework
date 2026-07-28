# 发现端与分析端缺陷修复 — 设计文档

日期：2026-07-28
状态：已批准
来源：2026-07-28 全面 code review（见当轮对话结论）

## 1. 背景与目标

框架的核心目标是：**找出处于极速上升趋势的开源项目，分析其创新或改进思路**。

Review 发现当前实现存在两类核心缺陷：

- **发现端**：topics 搜索按 stars 降序排序，系统性偏向成熟项目；star 历史从发现之日起才开始积累，velocity 信号存在 7-14 天空窗；评分模型四个信号中两个是伪信号（buzz 为常量、contributors 硬编码）；验证闭环无法度量漏检。
- **分析端**：无 LLM 时 heuristic 分析器生成与具体项目无关的模板化 opportunities 污染数据库；LLM 输入缺少 README，无法真正评估技术创新；incremental 调度无视变化每天重复分析同样的项目。

本 spec 覆盖全部 7 项修复，分两个 phase 实施：

- **Phase 1（发现端）**：找到真正"极速上升"的项目
- **Phase 2（分析端）**：让创新分析名副其实 + 工程杂项

两个 phase 互不依赖，各自独立可验证。

## 2. Phase 1：发现端

### 2.1 Topics 搜索转向新项目

现状：`discover.py` 的 topics 查询为 `topic:X language:Y stars:min..max`，`sort=stars`，每天重复返回同样的成熟 top-30，去重后增量趋近于零。

改法：

- 查询条件增加 `created:>{cutoff}`，cutoff 由 `sources.github.created_within_days` 配置，默认 730 天
- 排序改为 `sort=updated`
- trending 源和 ecosystem 源**不加** created 限制（老项目突然爆发由这两个源覆盖）

### 2.2 Stargazers 时间戳回溯（核心修复）

消除 velocity 信号的 7-14 天空窗。

**触发时机**：项目首次入库（star_history 中无该项目记录）时；存量无历史项目同样适用，分批消化。

**流程**：

1. 请求 `GET /repos/{owner}/{repo}/stargazers`，带 header `Accept: application/vnd.github.star+json`，`per_page=100`
2. 已知总 star 数 → 最后一页页码 = `ceil(stars/100)` → 从最后一页向前翻，收集每个 star 的 `starred_at`
3. 停止条件（任一满足）：
   - 当前页最早样本早于 35 天前
   - 已翻页数达到上限 `MAX_BACKFILL_PAGES`（默认 30 页 = 最近 3000 个 star；命中上限说明近 30 天涨幅 >3000，velocity 必然饱和，缺失更早期数据无碍判断）
   - 翻到第 1 页（repo 历史短于 35 天）
4. 按日期聚合累计 star 数，合成 star_history 行，`INSERT OR IGNORE` 写入（复用现有 `UNIQUE(project_id, sampled_at)` 约束；当日真实采样会自然覆盖合成值，语义一致）

**评分引擎零改动** —— 它只读 star_history，不区分数据是合成的还是采样的。

**降级**：API 失败 → 跳过该项目回溯，走原有空窗路径，不阻塞流水线。

**成本护栏**：

- 每日回溯项目数上限（可配，默认 100 个/天），避免首次对 712 个存量项目全量回溯时打爆 5000 次/小时的速率限额
- 复用现有 `_github_request` 的限流与重试机制

### 2.3 评分信号修复

现状：`community_buzz` 恒为常量 0.3；`novelty` 的 contributors 硬编码为 1；`activity` 的 PR merge rate 从未采集。四信号模型实际只有 velocity 一个真信号。

改法：

- **buzz 出局**：`config.yaml` 中 `community_buzz.weight` 置 0；其余权重归一化为 `star_velocity` 0.45 / `activity_index` 0.35 / `novelty_signal` 0.20。表结构不动（列保留，避免迁移）
- **contributors 实采**：评分前请求 `GET /repos/{}/commits?since={7天前}&per_page=100`，按 author 去重计数（novelty 阈值为 2，去重数 >2 即饱和，无需分页），写入已有的 `projects.contributor_count` 字段并传入 `calculate_novelty`。每项目 1 次 API 调用
- **PR merge rate**：继续留 None 走默认分支（采集成本高、信号弱，YAGNI）
- `reweight.py` 的 `COMPONENTS` 同步移除 `community_buzz`（历史 `prediction_outcomes` 行中的 buzz 列直接忽略）

### 2.4 召回率回溯

现状：`validate.py` 只记录被判为 early-burst 的项目，漏检（实际爆火但未达标/未被发现的项目）永远不进统计，闭环只能优化精确率。

改法：

- 对 **trending 源**发现、当时未达 early-burst 的项目，7 天后回看：若实际 star 增速 ≥ 同期 true_positive 判定阈值，记录 `outcome='false_negative'`
- `prediction_outcomes.outcome` 列无 CHECK 约束，直接可写新值，无需迁移
- `report.py` 的 Validation Metrics 区增加 FN 计数与 recall 展示

### 2.5 Phase 1 无 schema 变更

以上全部改动兼容现有数据库，无需表迁移。

## 3. Phase 2：分析端 + 工程杂项

### 3.1 README 注入

现状：LLM prompt 只有 name/description/topics/stars/轨迹/同类对比，无法真正评估技术创新，输出沦为对一句话描述的复述与泛化。

改法：

1. `analyze.py` 的 `get_project_data` 增加 README 抓取：`GET /repos/{}/readme`，base64 解码，取前 10000 字符
2. 注入 prompt 新占位符 `{readme_excerpt}`；`framework/prompts/ai_analyze.md` 增加 README 段落，明确指引 LLM 基于 README 中的技术架构、特性列表、路线图评估创新性
3. 降级：抓取失败 → 占位符填 `_README unavailable._`，分析照常进行
4. 不入库、不缓存，每次分析现取（1 次 API 调用/项目）

### 3.2 降级分析改造

现状：无 LLM 时 `generate_heuristic_analysis` 生成写死的模板化 opportunities（"LangChain 集成""企业版功能""插件市场"），与具体项目无关，污染 opportunities 表和报告。

改法：

- heuristic 保留**分类职能**：`tech_layer` / `application` / `ecosystem_position` 照常产出
- `opportunities` 返回空列表
- 主观字段（`problem_solved`、`innovation_summary`、`differentiation`、`market_timing`、`commercialization_path`）填空字符串，不再编造
- `analyzer_version` 区分来源：LLM 路径写 `'llm-v1'`，heuristic 路径写 `'heuristic-v1'`（当前统一写死 `'v1.0'`）
- 报告无需改动：Top Opportunities 自然只含 LLM 产出的机会

### 3.3 Incremental 变化触发

现状：`scheduler.py` 对 `active` 项目每天无条件生成 incremental 任务，重复分析烧 LLM 额度并堆积重复 analyses 行。

改法：

- `scheduled`（从未分析）项目：照常生成任务
- `active` 项目：仅当满足任一条件才生成任务 —
  - 近 7 天 star 涨幅 ≥ `scheduling.incremental.star_change_threshold`（默认 0.05，用 star_history 现算）
  - `last_commit_at` 在近 `scheduling.incremental.recent_commit_days` 天内（默认 3）

### 3.4 工程杂项

| 项 | 现状 | 改法 |
|---|---|---|
| run.sh 丢弃本地改动 | 检测到未提交改动后 `git checkout -- .` 静默丢弃 | 打印改动清单并 exit 1；CI fresh checkout 无改动，不受影响（run_bulk.sh 同步） |
| .gitignore 与提交意图矛盾 | `data/*.db`、`data/reports/*.md` 被 ignore，脚本却试图 add 它们，新报告永远进不了库 | 删除这两条 ignore 规则（`test_*.db*` 已单独覆盖测试残留） |
| filter 吞吐瓶颈 | `filter.py` 硬编码 LIMIT 50，662 条 backlog 需 14 轮 | 增加 `--limit` 参数（默认 50）；`run_bulk.sh` 循环调用直至 backlog 清空或达 `scheduling.bulk.max_per_day`（100） |

## 4. 验证方式

项目无测试框架，沿用"直接运行验证"惯例。每个 phase 完成后：

1. `discover.py --dry-run`：确认新 topics 查询命中的项目创建时间在 cutoff 窗口内
2. 选 1-2 个已知项目，手动核对回溯重建的 star 曲线与 GitHub 页面实际曲线一致
3. 无 LLM 跑一轮 `analyze.py`：确认 opportunities 为空、`analyzer_version='heuristic-v1'`
4. 有 LLM 跑一轮：确认报告中的机会与项目实际内容相关、prompt 包含 README 内容
5. `validate.py --metrics-only`：确认 false_negative 统计出现
6. 连跑两天 `run.sh`：确认 active 项目不再无条件重复生成任务

## 5. 明确不做的事（YAGNI）

- 不采集 PR merge rate（成本高、信号弱）
- 不做 anchor 反向发现（独立设计，见 `docs/superpowers/specs/anchor.md`）
- 不引入真正的预测模型（保留规则加权 + reweight 闭环）
- 不改数据库 schema
- 不新建测试框架
