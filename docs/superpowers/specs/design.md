# Open Source Project Opportunities Framework — Design Document

## 1. 项目定位

一个**配置驱动的通用框架**，通过 `config.yaml` 定义项目类别（如 AI、区块链等），自动发现该类别下处于**爆火初期阶段**的开源项目，利用 LLM 进行深度分析，识别创新思路和扩展机会。

与 pipeline 项目的核心差异：

| | Pipeline | Framework |
|---|---|---|
| 目标 | 找传统项目的贡献机会（原版 vs 移植版功能缺口） | 找创新项目的扩展机会（技术趋势、应用场景延伸） |
| 核心逻辑 | canonical 对比（Java 原版 → Go 移植版差距） | 早期信号检测 + 创新分析 |
| 分析重点 | issue/PR 深度挖掘、feature gap | 技术架构、差异化、商业化路径、生态位 |

## 2. 架构概览

```
                    config.yaml (类别定义)
                           |
        +------------------+------------------+
        |                  |                  |
   [发现阶段]          [过滤阶段]         [分析阶段]
   discover.py        filter.py         analyze.py
        |                  |                  |
        +------------------+------------------+
                           |
                    SQLite (framework.db)
                           |
        +------------------+------------------+
        |                  |                  |
   [调度阶段]          [评分阶段]         [报告阶段]
   schedule.py       scoring_engine.py   report.py
```

### 2.1 Stage 流水线

```
Stage 0: init_db.py    — 初始化/迁移数据库，崩溃恢复
Stage 1: discover.py   — 多源发现（topics + ecosystems + trending）
Stage 2: filter.py     — 语义过滤（启发式，规则来自 config）
Stage 3: schedule.py   — 任务调度（bulk / incremental）
Stage 4: analyze.py    — LLM 深度分析（prompt 模板化）
Stage 5: report.py     — 生成 Markdown 报告
```

## 3. 数据模型

### 3.1 核心表

**projects** — 发现的项目
- `id` (PK), `name`, `url`, `language`, `stars`, `open_issues`, `forks`
- `status`: discovered → scheduled → analyzing → active/filtered_skip
- `tech_layer`, `application` — 过滤阶段分类结果
- `prev_stars`, `prev_open_issues` — 增量分析基准快照
- `source`: github_topic | ecosystem | trending
- `first_seen_at`, `last_fetched_at`

**star_history** — star 数量时间序列
- 每日采样，用于计算 star velocity

**early_burst_signals** — 早期爆发信号
- `star_velocity_score`, `activity_index_score`, `community_buzz_score`, `novelty_score`
- `overall_score`, `is_early_burst`

**tasks** — 分析任务队列
- `task_type`: bulk | incremental
- `status`: pending → running → done/skipped

**analyses** — LLM 分析结果
- `tech_layer`, `application`, `problem_solved`, `innovation_summary`
- `differentiation`, `market_timing`, `overall_score`
- `ecosystem_position`, `commercialization_path` — AI 方向特有
- `CHECK(overall_score BETWEEN 1 AND 10)`

**opportunities** — 识别的扩展机会
- `opportunity_type`: product | tech | market | integration | business_model
- `impact_potential`, `difficulty`, `time_horizon`

### 3.2 状态机

```
projects:
  discovered ──[filter]──→ scheduled ──[analyze]──→ active
       |                      |
       └────[skip]────→ filtered_skip

tasks:
  pending ──[start]──→ running ──[done]──→ done
                          |
                          └─[fail]──→ skipped
```

## 4. 配置驱动设计

`config.yaml` 是框架的核心，定义"当前分析什么类别的项目"。

```yaml
category:
  name: "ai"                    # 类别标识
  display_name: "AI Projects"   # 展示名

dimensions:
  tech_layer:                   # 技术分层
    - foundation_model
    - inference_engine
    - ai_application
    - ai_toolchain
  application:                  # 应用场景
    - code_generation
    - image_generation
    - agent
    - ...

sources:
  github:
    topics: [...]               # GitHub topics 搜索
    languages: [...]            # 目标语言
    star_range: [50, 50000]     # star 范围
  ecosystems: [...]             # 生态组织
  trending:                     # GitHub Trending
    languages: [...]
    periods: ["daily", "weekly"]
  anchors: [...]                # 锚点反向发现

filters:
  skip_patterns: [...]          # 跳过模式
  category_keywords:            # 类别关键词（按类别）
    ai: [...]
  tech_layer_rules:             # 技术层分类规则
    foundation_model: [...]

scheduling:
  bulk: {batch_size: 20, max_per_day: 100}
  incremental: {max_per_day: 15}

early_burst:
  metrics:
    star_velocity: {weight: 0.35, ...}
    activity_index: {weight: 0.25, ...}
```

**扩展性**：更换类别时只需替换 `config.yaml`，无需修改代码。

## 5. 发现机制

### 5.1 三渠道发现

| 渠道 | 机制 | 覆盖范围 |
|---|---|---|
| GitHub Topics | `topic:X language:Y stars:min..max` | 已归类项目（90%+） |
| Ecosystem Orgs | `GET /orgs/{org}/repos` | 知名组织旗下项目 |
| GitHub Trending | HTML 解析 trending 页面 | 热门新兴项目 |

### 5.2 锚点反向发现（预留）

锚点是**搜索参照物**而非搜索目标。通过已知的重要项目/概念，反向搜索提及它们的新实现或变体。

```yaml
anchors:
  - name: "RAG"
    keywords: ["rag", "retrieval-augmented"]
  - name: "LangChain"
    keywords: ["langchain", "langgraph"]
```

搜索逻辑：`keyword in:name,description language:L stars:min..max`

## 6. 分析机制

### 6.1 Prompt 模板化

分析 prompt 不再硬编码在 `analyze.py` 中，而是从 `framework/prompts/ai_analyze.md` 读取。

```python
prompt_template = open('framework/prompts/ai_analyze.md').read()
prompt = prompt_template.format(
    name=project['name'],
    stars=project['stars'],
    ...
)
```

**好处**：
- 按类别切换 prompt（AI prompt vs 区块链 prompt）
- 无需改代码即可调优 prompt
- 版本控制 prompt 演进

### 6.2 AI 分析维度

| 维度 | 说明 |
|---|---|
| tech_layer | 技术分层（基础模型/推理引擎/应用/工具链） |
| application | 应用场景 |
| problem_solved | 解决的具体痛点 |
| innovation_summary | 核心创新点 |
| differentiation | 与竞品差异化 |
| market_timing | 时机判断和风险 |
| ecosystem_position | 生态位（基础层/中间件/应用层） |
| commercialization_path | 商业化路径 |
| opportunities | 3-5 个扩展机会 |

### 6.3 CLI Tool 兼容

支持两种 LLM 调用模式：

| 模式 | 命令示例 | Prompt 传递方式 |
|---|---|---|
| Claude | `claude --dangerously-skip-permissions` | `-p` 参数 |
| Cursor Agent | `agent --force` | stdin 重定向 |

自动检测：`'agent' in CLI_TOOL or 'cursor-agent' in CLI_TOOL`

## 7. 稳定性设计

### 7.1 数据库层

- **WAL 模式**：`PRAGMA journal_mode=WAL` — 读不阻塞写
- **busy_timeout**：`PRAGMA busy_timeout=5000` — 并发等待 5 秒
- **CHECK 约束**：`overall_score BETWEEN 1 AND 10`

### 7.2 进程层

- **flock 互斥锁**：`run.sh` / `run_bulk.sh` 共享锁文件，防止并发操作 DB
- **macOS 降级**：无 flock 时打印 WARN 继续执行

### 7.3 崩溃恢复

启动时自动执行：
```python
db.repair_analyzing_status()  # 重置卡在 analyzing 的项目
db.repair_orphan_records()    # 清理孤立记录
```

### 7.4 Git 工作流

- 检测本地未提交修改 → 打印 WARN → 丢弃 → 继续
- `git pull --rebase || echo WARN` — 网络失败不中断
- push 3 次重试：`sleep 10` → `pull --rebase` → 再 push

### 7.5 批量提交

`discover.py` 每 100 条 upserts commit 一次，防止 SIGKILL/OOM 导致全量回滚。

## 8. 调度机制

### 8.1 任务类型

| 类型 | 触发条件 | 用途 |
|---|---|---|
| bulk | 新发现项目首次分析 | 存量消化 |
| incremental | 已分析项目的增量跟踪 | 持续监控 |

### 8.2 增量调度（预留扩展）

基于 `prev_stars` / `prev_open_issues` 快照检测变化：
- stars 变化 > 5%
- issues 变化 > 10%
- 新提交（`last_commit_at > last_analyzed`）
- 新版本发布

## 9. 评分机制

### 9.1 早期爆发信号

```
overall_score = star_velocity * 0.35
              + activity_index * 0.25
              + community_buzz * 0.25
              + novelty_signal * 0.15
```

### 9.2 LLM 评分

`overall_score` 由 LLM 根据创新度、市场大小、执行力、团队背景综合评定（1-10）。

## 10. 报告机制

生成 Markdown 报告，包含：

1. **全局统计**：总跟踪数、早期爆发数、今日分析数、开放机会数
2. **技术栈分布**：按 tech_layer 分组统计
3. **早期爆发项目列表**：带评分和分类
4. **Top Opportunities**：按 impact_potential + overall_score 排序

## 11. 扩展性设计

### 11.1 新增类别

更换 `config.yaml` 即可支持新类别（如区块链）：

```yaml
category:
  name: "blockchain"
dimensions:
  tech_layer:
    - layer1
    - layer2
    - defi_protocol
sources:
  github:
    topics: ["blockchain", "ethereum", "smart-contracts"]
anchors:
  - name: "Zero-Knowledge"
    keywords: ["zk-snark", "zk-stark"]
```

### 11.2 新增发现渠道

在 `discover.py` 中新增方法，在 `run()` 中调用即可。

### 11.3 新增分析维度

1. 修改 `framework/prompts/{category}_analyze.md`
2. 修改 `analyze.py` 的 `validate_analysis_output()` 验证逻辑
3. 修改 `db.py` 的 analyses 表 schema

## 12. 部署模式

### 12.1 本地模式

```bash
./run.sh           # 增量分析（每日）
./run_bulk.sh 20   # 批量分析（首次/存量）
```

### 12.2 GitHub Actions 模式

`.github/workflows/discover.yml`：
- 定时触发（`schedule: cron`）
- 手动触发（`workflow_dispatch`）可选 incremental / bulk 模式
- 执行完整流水线后自动 push

## 13. 关键设计决策

### 为什么不用 pipeline 的 canonical 对比模式？

Pipeline 找的是"某语言缺少某功能"的贡献机会，核心参照是 Java/Python 原版实现。Framework 找的是"AI 创新项目的扩展机会"，核心参照是技术趋势和市场时机。业务目标不同，分析逻辑完全不同。

### 为什么 evidence 驱动评分没有完整迁移？

Pipeline 的 `scoring.py` 是针对"原版实现存在性"设计的规则引擎（value = canonical_impl_url + issue_reactions）。Framework 的评分对象是 AI 创新项目，评分维度（技术成熟度、市场潜力、创新性）与 pipeline 完全不同，需要为 AI 方向独立设计评分规则。

### 为什么 prompt 模板化而不是 agent 自主模式？

Pipeline 的 agent 自主模式（把完整指令传给 agent，agent 自己生成代码执行）适合重型分析（大量 GitHub API 调用、多轮对比）。Framework 的分析更轻量（单次 LLM 调用获取结构化 JSON），函数调用模式更可控、好调试、成本低。

### 为什么 SQLite 而不是 PostgreSQL？

项目数据量小（千级别项目），SQLite 足够。WAL 模式 + busy_timeout 已解决并发问题。单文件便于 Git 版本控制和 Actions 持久化。
