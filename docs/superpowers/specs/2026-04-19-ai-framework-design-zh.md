# 开源项目机会框架 - AI 类别设计规范

> **版本：** v1.1  
> **日期：** 2026-04-22  
> **目标：** 构建一个可配置的框架，用于发现早期爆发阶段的 AI 项目，分析其创新性，并识别扩展机会。

---

## 1. 概述

### 1.1 问题陈述

AI 开源领域发展迅速。项目可能在几天内从默默无闻到 trending。在**早期爆发阶段**（在饱和之前）识别有前景的项目，为以下群体提供重要价值：
- 寻找高影响力机会的贡献者
- 追踪新兴趋势的投资者
- 寻求创新工具的开发人员

### 1.2 解决方案方法

一个**配置驱动的框架**，具备以下功能：
1. 从多个来源（GitHub、HN、Reddit）发现 AI 项目
2. 基于速度、活跃度、热度和新颖性计算"早期爆发分数"
3. 使用 LLM 深入分析高潜力项目
4. 识别具有影响评估的扩展机会

### 1.3 关键设计决策

| 决策 | 理由 |
|------|------|
| 配置驱动（非插件） | 单类别聚焦更简单；以后可演进为插件 |
| SQLite + Markdown | 与参考流水线匹配；经过验证的用例 |
| 分离的批量/增量脚本 | 清晰的运营模式：批量处理积压，增量处理日常 |
| 二维分类（技术 × 应用） | AI 项目跨越多个维度；刚性分类会失败 |

---

## 2. 目录结构

```
opensource-project-opportunities-framework/
├── config.yaml                      # 主配置
├── requirements.txt                 # Python 依赖
│
├── framework/                       # 框架核心代码
│   ├── __init__.py
│   ├── core/                        # 核心模块
│   │   ├── __init__.py
│   │   ├── config_loader.py        # 解析 config.yaml
│   │   ├── db.py                   # 数据库操作
│   │   ├── scheduler.py            # 任务调度逻辑
│   │   └── scoring_engine.py       # 早期爆发分数计算
│   │
│   ├── stages/                      # 流水线阶段
│   │   ├── __init__.py
│   │   ├── init_db.py              # 数据库初始化
│   │   ├── discover.py             # 多源发现
│   │   ├── schedule.py             # 任务生成
│   │   └── report.py               # Markdown 报告生成
│   │
│   └── prompts/                     # LLM 提示词模板
│       ├── filter.md               # 阶段 3：语义过滤
│       └── ai_analyze.md           # 阶段 4：深度分析
│
├── data/                            # 数据目录
│   ├── .gitkeep
│   ├── framework.db                # SQLite 数据库
│   └── reports/                    # 每日 markdown 报告
│       └── .gitkeep
│
├── .github/
│   └── workflows/
│       └── discover.yml            # GitHub Actions 工作流
│
├── run.sh                          # 每日增量运行器
├── run_bulk.sh                     # 积压批量处理
└── .env.example                    # 环境模板
```


## 3. 配置 (config.yaml)

```yaml
# 类别配置
category:
  name: "ai"
  display_name: "AI 项目"
  version: "1.0.0"

# 二维分类
dimensions:
  tech_layer:
    - id: foundation_model
      name: "基础模型"
      description: "基础 LLM、多模态模型、领域特定模型"
    
    - id: training_framework
      name: "训练框架"
      description: "分布式训练、微调、RL 框架"
    
    - id: inference_engine
      name: "推理引擎"
      description: "模型服务、优化、量化"
    
    - id: ai_application
      name: "AI 应用"
      description: "基于 AI 的终端用户应用"
    
    - id: ai_toolchain
      name: "AI 工具链"
      description: "数据处理、评估、部署工具"

  application:
    - id: code_generation
      name: "代码生成"
    
    - id: image_generation
      name: "图像生成"
    
    - id: multimodal
      name: "多模态"
    
    - id: agent
      name: "智能体 / 自主系统"
    
    - id: data_annotation
      name: "数据标注与处理"
    
    - id: model_evaluation
      name: "模型评估与安全"

# 发现来源
sources:
  github:
    topics:
      - "artificial-intelligence"
      - "machine-learning"
      - "deep-learning"
      - "llm"
      - "large-language-models"
      - "generative-ai"
      - "ai-agents"
      - "diffusion-models"
      - "transformers"
      - "prompt-engineering"
    
    languages: ["Python", "TypeScript", "Rust", "Go", "Julia", "C++"]
    
    star_range: [50, 50000]
  
  trending:
    languages: ["python", "typescript", "rust", "go", "julia"]
    periods: ["daily", "weekly"]
  
  ecosystems:
    - "huggingface"
    - "openai"
    - "langchain-ai"
    - "microsoft"
    - "google-research"
    - "pytorch"
    - "tensorflow"
    - "ml-explore"
    - "vllm-project"
    - "ollama"
  
  community:
    hackernews:
      enabled: false              # 需要带 API 密钥的本地运行
      keywords: ["show hn", "llm", "ai model", "local llm", "ai agent"]
      min_score: 30
    
    reddit:
      enabled: false              # 需要带 API 密钥的本地运行
      subreddits: ["MachineLearning", "LocalLLaMA", "artificial", "OpenAI"]
      min_upvotes: 15

# 早期爆发检测
early_burst:
  enabled: true
  min_score: 0.65                    # 标记为早期爆发的阈值
  
  metrics:
    star_velocity:
      weight: 0.35
      thresholds:
        weekly_growth_rate: 0.15     # 15% 周增长率
        daily_absolute: 10           # 每天至少 10 个 star
    
    activity_index:
      weight: 0.25
      thresholds:
        issue_response_hours: 48
        pr_merge_rate: 0.3
        commit_frequency: 3          # 每周提交次数
    
    community_buzz:
      weight: 0.25
      thresholds:
        hn_mentions: 1
        reddit_mentions: 2
    
    novelty_signal:
      weight: 0.15
      thresholds:
        first_commit_within_months: 6
        unique_contributors_weekly: 2

# 过滤规则
filters:
  required:
    has_readme: true
    has_code: true
    min_contributors: 1              # AI 允许个人项目
  
  skip_patterns:
    - "awesome"
    - "awesome-list"
    - "curated-list"
    - "tutorial"
    - "course"
    - "examples"
    - "playground"
    - "demo"

# LLM 分析
analysis:
  template: "ai_analyze"
  output_language: "zh"
  max_projects_per_session: 10
  
  focus_areas:
    - problem_solved
    - innovation
    - differentiation
    - extension_opportunities
    - market_timing

# 调度
scheduling:
  bulk:
    batch_size: 20
    max_per_day: 100
  
  incremental:
    max_per_day: 15
  
  re_evaluate:
    interval_days: 7

# 报告
report:
  format: "markdown"
  language: "zh"
  sections:
    - summary
    - early_burst_projects
    - top_opportunities
    - trends

# 错误处理与弹性
resilience:
  github_api:
    max_retries: 3
    retry_delay_seconds: 60
    rate_limit_wait_seconds: 3600
  
  llm_analysis:
    max_retries: 2
    timeout_seconds: 300
    continue_on_error: true
  
  star_history:
    sample_interval_days: 1          # star 数量采样频率
    min_samples_for_velocity: 3      # 速度计算所需最小样本数
```


## 4. 数据库模式

### 4.1 projects（项目表）

```sql
CREATE TABLE projects (
    id TEXT PRIMARY KEY,                    -- "owner/repo"
    name TEXT,
    url TEXT,
    language TEXT,
    
    -- 指标（当前）
    stars INTEGER,
    open_issues INTEGER,
    forks INTEGER,
    
    -- 时间维度
    created_at TEXT,                        -- 仓库创建时间
    first_commit_at TEXT,
    last_commit_at TEXT,
    
    -- 分类
    topics TEXT,                            -- JSON 数组
    tech_layer TEXT,                        -- 来自 dimensions
    application TEXT,                       -- 来自 dimensions
    
    -- 发现元数据
    category TEXT,                          -- "ai"
    source TEXT,                            -- github_topic/trending/ecosystem/hn/reddit
    
    -- 过滤
    status TEXT,                            -- discovered/filtered_skip/scheduled/active
    filter_reason TEXT,
    
    -- 追踪
    first_seen_at TEXT,
    last_fetched_at TEXT,
    contributor_count INTEGER
);

CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_tech_layer ON projects(tech_layer);
CREATE INDEX idx_projects_application ON projects(application);
CREATE INDEX idx_projects_stars ON projects(stars DESC);
```

### 4.2 star_history（星标历史表 - 新增，用于速度计算）

GitHub API 不提供历史 star 数量。我们每日采样以构建历史。

```sql
CREATE TABLE star_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES projects(id),
    sampled_at TEXT,                        -- ISO8601 时间戳
    stars INTEGER,                          -- 采样时的 star 数量
    
    UNIQUE(project_id, sampled_at)
);

CREATE INDEX idx_star_history_project ON star_history(project_id, sampled_at DESC);
CREATE INDEX idx_star_history_sampled ON star_history(sampled_at);
```

**采样策略：**
- 每次 `discover.py` 运行时，对所有活跃项目的当前 star 数量进行采样
- 从样本计算速度：7天 = (当前 - 7天前样本)，30天同理
- 如果样本不足，速度分数设为 0.5（中性）

### 4.3 early_burst_signals（早期爆发信号表）

```sql
CREATE TABLE early_burst_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES projects(id),
    calculated_at TEXT,
    
    -- 组件分数（0-1）
    star_velocity_score REAL,
    activity_index_score REAL,
    community_buzz_score REAL,
    novelty_score REAL,
    
    -- 总体
    overall_score REAL,
    is_early_burst BOOLEAN,
    
    -- 原始数据用于调试
    signals_json TEXT,                      -- 原始指标
    
    UNIQUE(project_id, calculated_at)
);

CREATE INDEX idx_ebs_early_burst ON early_burst_signals(is_early_burst, overall_score DESC);
```

### 4.4 tasks（任务表）

```sql
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES projects(id),
    task_date TEXT,                         -- YYYY-MM-DD
    
    -- 任务类型
    task_type TEXT,                         -- bulk/incremental/re_evaluate
    priority_score REAL,                    -- 用于排序
    trigger_reason TEXT,
    
    -- 状态
    status TEXT,                            -- pending/running/done/skipped
    created_at TEXT,
    started_at TEXT,
    finished_at TEXT,
    
    -- 结果摘要
    early_burst_score REAL,
    opportunities_found INTEGER
);

CREATE INDEX idx_tasks_date_status ON tasks(task_date, status);
CREATE INDEX idx_tasks_project ON tasks(project_id);
```

### 4.5 analyses（分析表）

```sql
CREATE TABLE analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES projects(id),
    analyzed_at TEXT,
    
    -- 分类（由 LLM 确认）
    tech_layer TEXT,
    application TEXT,
    
    -- 分析内容
    problem_solved TEXT,                    -- 解决什么问题
    innovation_summary TEXT,                -- 核心创新
    differentiation TEXT,                   -- 与竞争对手的区别
    market_timing TEXT,                     -- 为什么是现在
    
    -- 评分
    overall_score INTEGER,                  -- 1-10
    
    -- 元数据
    analyzer_version TEXT                   -- 提示词/模板版本
);

CREATE INDEX idx_analyses_project ON analyses(project_id);
```

### 4.6 opportunities（机会表）

```sql
CREATE TABLE opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES projects(id),
    
    -- 来源追踪
    source_analysis_date TEXT,
    
    -- 机会详情
    opportunity_type TEXT,                  -- product/tech/market/integration/business_model
    title TEXT,
    description TEXT,
    
    -- 评估
    impact_potential TEXT,                  -- high/medium/low
    difficulty TEXT,
    time_horizon TEXT,                      -- short/medium/long
    
    -- 洞察
    key_insight TEXT,
    evidence TEXT,                          -- JSON: 支持事实
    
    -- 生命周期
    first_seen_at TEXT,
    last_seen_at TEXT,
    status TEXT DEFAULT 'open'              -- open/claimed/stale/realized
);

CREATE INDEX idx_opportunities_project ON opportunities(project_id);
CREATE INDEX idx_opportunities_type ON opportunities(opportunity_type);
```


## 5. 核心模块

### 5.1 config_loader.py

**职责：** 加载和验证 config.yaml

```python
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
import yaml
import os

@dataclass
class CategoryConfig:
    name: str
    display_name: str
    version: str

@dataclass
class DimensionsConfig:
    tech_layer: List[Dict]
    application: List[Dict]

@dataclass
class EarlyBurstConfig:
    enabled: bool
    min_score: float
    metrics: Dict[str, Any]

@dataclass
class ResilienceConfig:
    github_api: Dict[str, int]
    llm_analysis: Dict[str, Any]
    star_history: Dict[str, int]

class ConfigLoader:
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            config_path = os.path.join(base_dir, 'config.yaml')
        self.config_path = config_path
        self._config = None
    
    def load(self) -> Dict[str, Any]:
        if self._config is None:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f)
        return self._config
    
    def get_category(self) -> CategoryConfig:
        cat = self.load()['category']
        return CategoryConfig(**cat)
    
    def get_dimensions(self) -> DimensionsConfig:
        dims = self.load()['dimensions']
        return DimensionsConfig(
            tech_layer=dims['tech_layer'],
            application=dims['application']
        )
    
    def get_early_burst_config(self) -> EarlyBurstConfig:
        eb = self.load()['early_burst']
        return EarlyBurstConfig(**eb)
    
    def get_resilience_config(self) -> ResilienceConfig:
        res = self.load().get('resilience', {})
        return ResilienceConfig(
            github_api=res.get('github_api', {'max_retries': 3, 'retry_delay_seconds': 60}),
            llm_analysis=res.get('llm_analysis', {'max_retries': 2, 'timeout_seconds': 300}),
            star_history=res.get('star_history', {'sample_interval_days': 1, 'min_samples_for_velocity': 3})
        )
    
    def get_github_topics(self) -> List[str]:
        return self.load()['sources']['github']['topics']
    
    def get_star_range(self) -> tuple:
        return tuple(self.load()['sources']['github']['star_range'])
    
    def get_ecosystems(self) -> List[str]:
        return self.load()['sources']['ecosystems']
    
    def get_trending_languages(self) -> List[str]:
        return self.load()['sources']['trending']['languages']
    
    def get_filters(self) -> Dict:
        return self.load()['filters']
    
    def get_scheduling_config(self) -> Dict:
        return self.load()['scheduling']
```


class ScoringEngine:
    def __init__(self, config: EarlyBurstConfig):
        self.config = config
    
    def calculate_star_velocity(self, 
                                current: int, 
                                past_7d: Optional[int],
                                past_30d: Optional[int]) -> float:
        """Calculate star velocity score (0-1) based on growth rate."""
        if past_7d is None or past_7d == 0 or current <= past_7d:
            return 0.5  # Neutral if no historical data
        
        weekly_growth = (current - past_7d) / past_7d
        daily_absolute = (current - past_7d) / 7
        
        threshold = self.config.metrics['star_velocity']['thresholds']
        target_weekly = threshold['weekly_growth_rate']
        target_daily = threshold['daily_absolute']
        
        # Score based on how close to target
        weekly_score = min(weekly_growth / target_weekly, 1.5)  # Cap at 1.5x for bonus
        daily_score = min(daily_absolute / target_daily, 1.5)
        
        # Weight weekly more heavily as it's more reliable
        return min((weekly_score * 0.7 + daily_score * 0.3), 1.0)
    
    def calculate_activity_index(self,
                                  open_issues: int,
                                  commit_frequency: float,
                                  pr_merge_rate: Optional[float] = None) -> float:
        """Calculate activity index score (0-1)."""
        threshold = self.config.metrics['activity_index']['thresholds']
        
        score = 0.0
        # Commit frequency (0-0.4)
        if commit_frequency >= threshold['commit_frequency']:
            score += 0.4
        elif commit_frequency >= threshold['commit_frequency'] * 0.5:
            score += 0.2
        else:
            score += 0.1
        
        # PR merge rate (0-0.3)
        if pr_merge_rate is not None:
            if pr_merge_rate >= threshold['pr_merge_rate']:
                score += 0.3
            elif pr_merge_rate >= threshold['pr_merge_rate'] * 0.5:
                score += 0.15
        else:
            score += 0.15  # Unknown gets neutral
        
        # Open issues as proxy for engagement (0-0.3)
        if open_issues >= 10:
            score += 0.3
        elif open_issues >= 3:
            score += 0.2
        elif open_issues > 0:
            score += 0.1
        
        return min(score, 1.0)
    
    def calculate_community_buzz(self, 
                                  hn_mentions: int = 0,
                                  reddit_mentions: int = 0) -> float:
        """Calculate community buzz score (0-1)."""
        threshold = self.config.metrics['community_buzz']['thresholds']
        
        hn_score = min(hn_mentions / threshold['hn_mentions'], 1.0) if threshold['hn_mentions'] > 0 else 0
        reddit_score = min(reddit_mentions / threshold['reddit_mentions'], 1.0) if threshold['reddit_mentions'] > 0 else 0
        
        # Weighted combination
        return min(hn_score * 0.6 + reddit_score * 0.4, 1.0)
    
    def calculate_novelty(self,
                          first_commit_at: Optional[str],
                          unique_contributors_weekly: int = 0) -> float:
        """Calculate novelty score (0-1) - newer projects score higher."""
        if first_commit_at is None:
            return 0.5
        
        try:
            first_commit = datetime.fromisoformat(first_commit_at.replace('Z', '+00:00'))
            months_old = (datetime.now(timezone.utc) - first_commit).days / 30
        except:
            return 0.5
        
        threshold = self.config.metrics['novelty_signal']['thresholds']
        max_months = threshold['first_commit_within_months'] * 2
        
        # Age score: 1.0 at 0 months, 0.0 at max_months
        age_score = max(0, 1.0 - (months_old / max_months))
        
        # Contributor growth score
        contrib_threshold = threshold['unique_contributors_weekly']
        contrib_score = min(unique_contributors_weekly / contrib_threshold, 1.0) if contrib_threshold > 0 else 0
        
        return min(age_score * 0.6 + contrib_score * 0.4, 1.0)
    
    def calculate_overall(self, 
                          star_velocity: float,
                          activity: float,
                          buzz: float,
                          novelty: float) -> Dict[str, Any]:
        """Calculate weighted overall score and return breakdown."""
        weights = {
            'star_velocity': self.config.metrics['star_velocity']['weight'],
            'activity_index': self.config.metrics['activity_index']['weight'],
            'community_buzz': self.config.metrics['community_buzz']['weight'],
            'novelty_signal': self.config.metrics['novelty_signal']['weight']
        }
        
        overall = (
            star_velocity * weights['star_velocity'] +
            activity * weights['activity_index'] +
            buzz * weights['community_buzz'] +
            novelty * weights['novelty_signal']
        )
        
        return {
            'star_velocity_score': star_velocity,
            'activity_index_score': activity,
            'community_buzz_score': buzz,
            'novelty_score': novelty,
            'overall_score': overall,
            'is_early_burst': overall >= self.config.min_score
        }
```


### 5.3 db.py

**职责：** 数据库操作和连接管理

```python
import sqlite3
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone


class Database:
    """SQLite database manager for the framework."""
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            db_path = os.path.join(base_dir, 'data', 'framework.db')
        self.db_path = db_path
        # Ensure data directory exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    def get_conn(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_tables(self):
        """Initialize all database tables."""
        conn = self.get_conn()
        try:
            self._create_projects(conn)
            self._create_star_history(conn)
            self._create_early_burst_signals(conn)
            self._create_tasks(conn)
            self._create_analyses(conn)
            self._create_opportunities(conn)
            conn.commit()
        finally:
            conn.close()
    
    def _create_projects(self, conn: sqlite3.Connection):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT,
                url TEXT,
                language TEXT,
                stars INTEGER,
                open_issues INTEGER,
                forks INTEGER,
                created_at TEXT,
                first_commit_at TEXT,
                last_commit_at TEXT,
                topics TEXT,
                tech_layer TEXT,
                application TEXT,
                category TEXT,
                source TEXT,
                status TEXT DEFAULT 'discovered',
                filter_reason TEXT,
                first_seen_at TEXT,
                last_fetched_at TEXT,
                contributor_count INTEGER
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_tech ON projects(tech_layer)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_app ON projects(application)")
    
    def _create_star_history(self, conn: sqlite3.Connection):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS star_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT REFERENCES projects(id),
                sampled_at TEXT,
                stars INTEGER,
                UNIQUE(project_id, sampled_at)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sh_project ON star_history(project_id, sampled_at DESC)")
    
    def _create_early_burst_signals(self, conn: sqlite3.Connection):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS early_burst_signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT REFERENCES projects(id),
                calculated_at TEXT,
                star_velocity_score REAL,
                activity_index_score REAL,
                community_buzz_score REAL,
                novelty_score REAL,
                overall_score REAL,
                is_early_burst BOOLEAN,
                signals_json TEXT,
                UNIQUE(project_id, calculated_at)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ebs_burst ON early_burst_signals(is_early_burst, overall_score DESC)")
    
    def _create_tasks(self, conn: sqlite3.Connection):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT REFERENCES projects(id),
                task_date TEXT,
                task_type TEXT,
                priority_score REAL,
                trigger_reason TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT,
                started_at TEXT,
                finished_at TEXT,
                early_burst_score REAL,
                opportunities_found INTEGER
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_date ON tasks(task_date, status)")
    
    def _create_analyses(self, conn: sqlite3.Connection):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT REFERENCES projects(id),
                analyzed_at TEXT,
                tech_layer TEXT,
                application TEXT,
                problem_solved TEXT,
                innovation_summary TEXT,
                differentiation TEXT,
                market_timing TEXT,
                overall_score INTEGER,
                analyzer_version TEXT
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_analyses_project ON analyses(project_id)")
    
    def _create_opportunities(self, conn: sqlite3.Connection):
        conn.execute("""
            CREATE TABLE IF NOT EXISTS opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT REFERENCES projects(id),
                source_analysis_date TEXT,
                opportunity_type TEXT,
                title TEXT,
                description TEXT,
                impact_potential TEXT,
                difficulty TEXT,
                time_horizon TEXT,
                key_insight TEXT,
                evidence TEXT,
                first_seen_at TEXT,
                last_seen_at TEXT,
                status TEXT DEFAULT 'open'
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_opp_project ON opportunities(project_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_opp_type ON opportunities(opportunity_type)")
    
    # Utility methods for common operations
    def get_project_star_history(self, project_id: str, days: int = 30) -> List[Dict]:
        """Get star history for a project over last N days."""
        conn = self.get_conn()
        try:
            cursor = conn.execute("""
                SELECT * FROM star_history 
                WHERE project_id = ? 
                AND sampled_at >= datetime('now', '-{} days')
                ORDER BY sampled_at DESC
            """.format(days), (project_id,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
    
    def sample_star_count(self, project_id: str, stars: int):
        """Record a star count sample."""
        conn = self.get_conn()
        try:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute("""
                INSERT OR REPLACE INTO star_history (project_id, sampled_at, stars)
                VALUES (?, date(?), ?)
            """, (project_id, now, stars))
            conn.commit()
        finally:
            conn.close()
```


### 5.4 scheduler.py

**职责：** 生成和管理分析任务

```python
import sqlite3
from datetime import datetime, timezone
from enum import Enum
from typing import List, Dict, Optional


class TaskType(Enum):
    BULK = "bulk"
    INCREMENTAL = "incremental"
    RE_EVALUATE = "re_evaluate"


class Scheduler:
    """Task scheduler for the analysis pipeline."""
    
    def __init__(self, db_path: str, config: Dict):
        self.db_path = db_path
        self.config = config
    
    def get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def generate_bulk_tasks(self, date: str, batch_size: int) -> int:
        """
        Generate bulk tasks for undiscovered projects.
        Priority: projects with highest early-burst scores first.
        """
        conn = self.get_conn()
        try:
            # Find projects in 'discovered' status not yet scheduled
            cur = conn.execute("""
                SELECT p.id, COALESCE(e.overall_score, 0.5) as burst_score
                FROM projects p
                LEFT JOIN early_burst_signals e ON p.id = e.project_id
                WHERE p.status = 'discovered'
                AND p.id NOT IN (
                    SELECT project_id FROM tasks WHERE task_type = 'bulk'
                )
                ORDER BY burst_score DESC, p.stars DESC
                LIMIT ?
            """, (batch_size,))
            
            count = 0
            for row in cur.fetchall():
                conn.execute("""
                    INSERT INTO tasks (project_id, task_date, task_type,
                                     priority_score, trigger_reason, status, created_at)
                    VALUES (?, ?, 'bulk', ?, 'backlog_processing', 'pending', ?)
                """, (row['id'], date, row['burst_score'],
                      datetime.now(timezone.utc).isoformat()))
                count += 1
            
            conn.commit()
            return count
        finally:
            conn.close()
    
    def generate_incremental_tasks(self, date: str, max_tasks: int) -> int:
        """
        Generate tasks for new discoveries (status='scheduled').
        These are projects that passed filtering and are ready for analysis.
        """
        conn = self.get_conn()
        try:
            cur = conn.execute("""
                SELECT p.id, COALESCE(e.overall_score, 0.5) as burst_score
                FROM projects p
                LEFT JOIN early_burst_signals e ON p.id = e.project_id
                WHERE p.status = 'scheduled'
                AND p.id NOT IN (
                    SELECT project_id FROM tasks WHERE task_date = ?
                )
                ORDER BY burst_score DESC
                LIMIT ?
            """, (date, max_tasks))
            
            count = 0
            for row in cur.fetchall():
                conn.execute("""
                    INSERT INTO tasks (project_id, task_date, task_type,
                                     priority_score, trigger_reason, status, created_at)
                    VALUES (?, ?, 'incremental', ?, 'new_discovery', 'pending', ?)
                """, (row['id'], date, row['burst_score'],
                      datetime.now(timezone.utc).isoformat()))
                count += 1
            
            conn.commit()
            return count
        finally:
            conn.close()
    
    def get_pending_tasks(self, date: str, task_type: Optional[str] = None) -> List[Dict]:
        """Get pending tasks for a date."""
        conn = self.get_conn()
        try:
            if task_type:
                cur = conn.execute("""
                    SELECT * FROM tasks 
                    WHERE task_date = ? AND status = 'pending' AND task_type = ?
                    ORDER BY priority_score DESC
                """, (date, task_type))
            else:
                cur = conn.execute("""
                    SELECT * FROM tasks 
                    WHERE task_date = ? AND status = 'pending'
                    ORDER BY priority_score DESC
                """, (date,))
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()
    
    def mark_task_running(self, task_id: int):
        """Mark a task as running."""
        conn = self.get_conn()
        try:
            conn.execute("""
                UPDATE tasks SET status = 'running', started_at = ?
                WHERE id = ?
            """, (datetime.now(timezone.utc).isoformat(), task_id))
            conn.commit()
        finally:
            conn.close()
    
    def mark_task_done(self, task_id: int, opportunities_found: int = 0):
        """Mark a task as completed."""
        conn = self.get_conn()
        try:
            conn.execute("""
                UPDATE tasks SET status = 'done', finished_at = ?, opportunities_found = ?
                WHERE id = ?
            """, (datetime.now(timezone.utc).isoformat(), opportunities_found, task_id))
            conn.commit()
        finally:
            conn.close()
```


## 6. 流水线阶段

### 6.1 init_db.py

**Responsibility:** Initialize database tables

**Usage:** `python framework/stages/init_db.py`

Simply calls `Database.init_tables()`.

### 6.2 discover.py

**Responsibility:** Multi-source project discovery with rate limiting and error handling

**Key Features:**
- GitHub API with retry logic and rate limit handling
- Star history sampling for velocity calculation
- Dry-run mode for testing
- Error resilience (continues on individual source failures)

**Complete Implementation:**

```python
#!/usr/bin/env python3
"""
Stage 1: Discover AI projects from multiple sources.
Samples star counts to build velocity history.
"""
import os
import sys
import json
import time
import argparse
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Set

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from framework.core.config_loader import ConfigLoader
from framework.core.db import Database
from framework.core.scoring_engine import ScoringEngine


# GitHub API Configuration
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
HEADERS = {
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28'
}
if GITHUB_TOKEN:
    HEADERS['Authorization'] = f'Bearer {GITHUB_TOKEN}'

# Rate limiting state
_last_request_time = 0
_search_request_count = 0
_search_reset_time = 0


class GitHubAPIError(Exception):
    """GitHub API error with retry info."""
    def __init__(self, message: str, status_code: int = None, retry_after: int = None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


class DiscoverStage:
    """Multi-source project discovery stage."""
    
    def __init__(self, config: ConfigLoader, db: Database):
        self.config = config
        self.db = db
        self.scoring = ScoringEngine(config.get_early_burst_config())
        self.resilience = config.get_resilience_config()
        self.star_min, self.star_max = config.get_star_range()
    
    def _github_request(self, url: str, params: Optional[Dict] = None, 
                       is_search: bool = False) -> Dict:
        """
        Make GitHub API request with rate limit handling.
        
        - Search API: 30 requests/minute (2s delay)
        - Core API: 5000 requests/hour with token
        """
        global _last_request_time, _search_request_count
        
        # Rate limiting for search API
        if is_search:
            elapsed = time.time() - _last_request_time
            if elapsed < 2:
                time.sleep(2 - elapsed)
        else:
            # Small delay for core API to be polite
            elapsed = time.time() - _last_request_time
            if elapsed < 0.5:
                time.sleep(0.5 - elapsed)
        
        for attempt in range(self.resilience.github_api['max_retries']):
            try:
                response = requests.get(
                    url, 
                    headers=HEADERS, 
                    params=params, 
                    timeout=30
                )
                _last_request_time = time.time()
                
                # Handle rate limiting
                if response.status_code == 403 and 'rate limit' in response.text.lower():
                    reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                    wait_time = max(reset_time - int(time.time()), 60)
                    print(f"  Rate limited. Waiting {wait_time}s...")
                    time.sleep(min(wait_time, self.resilience.github_api['rate_limit_wait_seconds']))
                    continue
                
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    print(f"  Too many requests. Waiting {retry_after}s...")
                    time.sleep(min(retry_after, self.resilience.github_api['retry_delay_seconds']))
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                if attempt < self.resilience.github_api['max_retries'] - 1:
                    wait = self.resilience.github_api['retry_delay_seconds'] * (attempt + 1)
                    print(f"  Request failed (attempt {attempt + 1}). Waiting {wait}s...")
                    time.sleep(wait)
                else:
                    raise GitHubAPIError(f"Failed after {attempt + 1} attempts: {e}")
        
        return {}
    
    def _should_skip_repo(self, repo: Dict) -> tuple[bool, str]:
        """Check if repository should be skipped based on filters."""
        filters = self.config.get_filters()
        
        stars = repo.get('stargazers_count', 0)
        if stars < self.star_min:
            return True, f"stars_too_few:{stars}"
        if stars > self.star_max:
            return True, f"stars_too_many:{stars}"
        
        if repo.get('archived'):
            return True, "archived"
        
        # Check stale (no commits in 180 days)
        pushed = repo.get('pushed_at', '')
        if pushed:
            try:
                pushed_dt = datetime.fromisoformat(pushed.replace('Z', '+00:00'))
                stale_cutoff = datetime.now(timezone.utc) - timedelta(days=180)
                if pushed_dt < stale_cutoff:
                    return True, f"stale_since:{pushed[:10]}"
            except:
                pass
        
        # Check skip patterns
        name = repo.get('name', '').lower()
        desc = (repo.get('description') or '').lower()
        for pattern in filters['skip_patterns']:
            if pattern in name or pattern in desc:
                return True, f"skip_pattern:{pattern}"
        
        if repo.get('fork'):
            return True, "is_fork"
        
        return False, ""
    
    def _upsert_project(self, repo: Dict, source: str, signal: str):
        """Insert or update project in database."""
        conn = self.db.get_conn()
        try:
            now = datetime.now(timezone.utc).isoformat()
            project_id = repo['full_name']
            
            # Get latest release info
            release = None
            release_at = None
            try:
                rel_url = f"https://api.github.com/repos/{project_id}/releases/latest"
                rel_resp = requests.get(rel_url, headers=HEADERS, timeout=10)
                if rel_resp.status_code == 200:
                    rel_data = rel_resp.json()
                    release = rel_data.get('tag_name')
                    release_at = rel_data.get('published_at')
            except:
                pass
            
            # Insert or update project
            conn.execute("""
                INSERT INTO projects (
                    id, name, url, language, stars, open_issues, forks,
                    created_at, last_commit_at, topics, description,
                    category, source, status, first_seen_at, last_fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'discovered', ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    stars = excluded.stars,
                    open_issues = excluded.open_issues,
                    forks = excluded.forks,
                    last_commit_at = excluded.last_commit_at,
                    topics = excluded.topics,
                    description = excluded.description,
                    last_fetched_at = excluded.last_fetched_at,
                    source = CASE 
                        WHEN projects.source IN ('anchor', 'ecosystem') THEN projects.source
                        ELSE excluded.source 
                    END
            """, (
                project_id,
                repo.get('name'),
                repo.get('html_url'),
                repo.get('language'),
                repo.get('stargazers_count', 0),
                repo.get('open_issues_count', 0),
                repo.get('forks_count', 0),
                repo.get('created_at'),
                repo.get('pushed_at'),
                json.dumps(repo.get('topics', [])),
                repo.get('description', '')[:500],
                'ai',
                source,
                now if not conn.execute("SELECT 1 FROM projects WHERE id = ?", (project_id,)).fetchone() else None,
                now
            ))
            
            conn.commit()
            return project_id
        finally:
            conn.close()
    
    def _sample_star_count(self, project_id: str, stars: int):
        """Sample current star count for velocity tracking."""
        self.db.sample_star_count(project_id, stars)
    
    def _calculate_and_store_burst_score(self, project_id: str):
        """Calculate early-burst score from sampled data."""
        conn = self.db.get_conn()
        try:
            # Get current project info
            proj = conn.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            ).fetchone()
            
            if not proj:
                return
            
            # Get star history
            current_stars = proj['stars']
            history = self.db.get_project_star_history(project_id, days=35)
            
            # Find stars from 7d and 30d ago
            stars_7d_ago = None
            stars_30d_ago = None
            
            now = datetime.now(timezone.utc)
            for sample in history:
                sample_date = datetime.fromisoformat(sample['sampled_at'].replace('Z', '+00:00'))
                days_ago = (now - sample_date).days
                
                if 6 <= days_ago <= 8 and stars_7d_ago is None:
                    stars_7d_ago = sample['stars']
                if 28 <= days_ago <= 32 and stars_30d_ago is None:
                    stars_30d_ago = sample['stars']
            
            # Calculate scores
            velocity_score = self.scoring.calculate_star_velocity(
                current_stars, stars_7d_ago, stars_30d_ago
            )
            activity_score = self.scoring.calculate_activity_index(
                proj['open_issues'] or 0, 3  # Default commit freq
            )
            novelty_score = self.scoring.calculate_novelty(
                proj['created_at'], 1
            )
            buzz_score = 0.3  # Default (no community data yet)
            
            result = self.scoring.calculate_overall(
                velocity_score, activity_score, buzz_score, novelty_score
            )
            
            # Store result
            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute("""
                INSERT INTO early_burst_signals (
                    project_id, calculated_at,
                    star_velocity_score, activity_index_score,
                    community_buzz_score, novelty_score,
                    overall_score, is_early_burst, signals_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                project_id, now_iso,
                result['star_velocity_score'],
                result['activity_index_score'],
                result['community_buzz_score'],
                result['novelty_score'],
                result['overall_score'],
                result['is_early_burst'],
                json.dumps({
                    'stars_7d_ago': stars_7d_ago,
                    'stars_30d_ago': stars_30d_ago,
                    'current_stars': current_stars
                })
            ))
            conn.commit()
            
        finally:
            conn.close()
    
    def discover_topics(self) -> List[Dict]:
        """Discover from GitHub topics."""
        results = []
        topics = self.config.get_github_topics()
        languages = self.config.config['sources']['github']['languages']
        
        print(f"Discovering from {len(topics)} topics x {len(languages)} languages...")
        
        for topic in topics:
            for lang in languages:
                query = f"topic:{topic} language:{lang} stars:{self.star_min}..{self.star_max}"
                url = "https://api.github.com/search/repositories"
                
                try:
                    data = self._github_request(url, {"q": query, "sort": "stars", "per_page": 30}, is_search=True)
                    
                    for repo in data.get('items', []):
                        skip, reason = self._should_skip_repo(repo)
                        if not skip:
                            results.append({
                                'repo': repo,
                                'source': 'github_topic',
                                'signal': f"{topic}/{lang}"
                            })
                        else:
                            print(f"  Skip ({reason}): {repo['full_name']}")
                            
                except GitHubAPIError as e:
                    print(f"  Error searching {topic}/{lang}: {e}")
                    continue
        
        return results
    
    def discover_ecosystems(self) -> List[Dict]:
        """Discover from ecosystem organizations."""
        results = []
        ecosystems = self.config.get_ecosystems()
        
        print(f"Discovering from {len(ecosystems)} ecosystems...")
        
        for org in ecosystems:
            page = 1
            while page <= 5:  # Limit to 500 repos per org
                url = f"https://api.github.com/orgs/{org}/repos"
                params = {"per_page": 100, "page": page, "sort": "updated"}
                
                try:
                    repos = self._github_request(url, params)
                    
                    if not repos:
                        break
                    
                    for repo in repos:
                        stars = repo.get('stargazers_count', 0)
                        if stars < self.star_min or stars > self.star_max:
                            continue
                        
                        skip, reason = self._should_skip_repo(repo)
                        if not skip:
                            results.append({
                                'repo': repo,
                                'source': 'ecosystem',
                                'signal': org
                            })
                    
                    page += 1
                    
                except GitHubAPIError as e:
                    print(f"  Error fetching {org}: {e}")
                    break
        
        return results
    
    def run(self, dry_run: bool = False):
        """Execute full discovery process."""
        print("=== Stage 1: Discover ===")
        print(f"Star range: {self.star_min} - {self.star_max}")
        print(f"Dry run: {dry_run}")
        print()
        
        all_results = []
        
        # Source 1: Topics
        print("Source 1: GitHub Topics...")
        all_results.extend(self.discover_topics())
        print(f"  Found: {len(all_results)} projects")
        
        # Source 2: Ecosystems
        print("Source 2: Ecosystem Organizations...")
        eco_results = self.discover_ecosystems()
        all_results.extend(eco_results)
        print(f"  Found: {len(eco_results)} projects")
        
        # Deduplicate
        seen: Set[str] = set()
        unique_results = []
        for item in all_results:
            pid = item['repo']['full_name']
            if pid not in seen:
                seen.add(pid)
                unique_results.append(item)
        
        print(f"\nTotal unique projects: {len(unique_results)}")
        
        if dry_run:
            print("\nDry run - not writing to database")
            for item in unique_results[:10]:
                print(f"  {item['repo']['full_name']} ({item['source']})")
            return
        
        # Store results
        print("\nStoring projects...")
        stored_count = 0
        for item in unique_results:
            try:
                project_id = self._upsert_project(item['repo'], item['source'], item['signal'])
                self._sample_star_count(project_id, item['repo']['stargazers_count'])
                self._calculate_and_store_burst_score(project_id)
                stored_count += 1
            except Exception as e:
                print(f"  Error storing {item['repo']['full_name']}: {e}")
        
        print(f"\nStored {stored_count} projects")
        
        # Sample star counts for existing active projects
        print("\nSampling star history for existing projects...")
        conn = self.db.get_conn()
        try:
            active_projects = conn.execute(
                "SELECT id, stars FROM projects WHERE status IN ('scheduled', 'active')"
            ).fetchall()
            
            for proj in active_projects:
                self._sample_star_count(proj['id'], proj['stars'])
            
            print(f"  Sampled {len(active_projects)} existing projects")
        finally:
            conn.close()


def main():
    parser = argparse.ArgumentParser(description="Discover AI projects")
    parser.add_argument('--dry-run', action='store_true', help="Don't write to database")
    args = parser.parse_args()
    
    config = ConfigLoader()
    db = Database()
    
    stage = DiscoverStage(config, db)
    stage.run(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
```


### 6.3 schedule.py

**Responsibility:** Generate tasks from discovered projects

```python
#!/usr/bin/env python3
"""Stage 2: Schedule analysis tasks."""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from framework.core.config_loader import ConfigLoader
from framework.core.db import Database
from framework.core.scheduler import Scheduler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['bulk', 'incremental'], default='incremental')
    parser.add_argument('--batch-size', type=int, default=20)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    
    config = ConfigLoader()
    db = Database()
    scheduler = Scheduler(db.db_path, config.get_scheduling_config())
    
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    if args.mode == 'bulk':
        count = scheduler.generate_bulk_tasks(today, args.batch_size)
        print(f"Generated {count} bulk tasks for {today}")
    else:
        max_tasks = config.get_scheduling_config()['incremental']['max_per_day']
        count = scheduler.generate_incremental_tasks(today, max_tasks)
        print(f"Generated {count} incremental tasks for {today}")


if __name__ == '__main__':
    main()
```

### 6.4 report.py

**Responsibility:** Generate daily Markdown report

```python
#!/usr/bin/env python3
"""Stage 5: Generate daily Markdown report."""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from framework.core.db import Database


class ReportGenerator:
    """Generate Markdown reports from analysis results."""
    
    def __init__(self, db: Database):
        self.db = db
    
    def generate(self, date: str):
        conn = self.db.get_conn()
        try:
            # Get early-burst projects
            projects = conn.execute("""
                SELECT p.*, e.overall_score, e.star_velocity_score, 
                       e.activity_index_score, e.novelty_score
                FROM projects p
                JOIN early_burst_signals e ON p.id = e.project_id
                WHERE e.is_early_burst = 1
                AND date(e.calculated_at) = ?
                ORDER BY e.overall_score DESC
            """, (date,)).fetchall()
            
            # Get top opportunities
            opportunities = conn.execute("""
                SELECT o.*, p.name as project_name, p.url as project_url
                FROM opportunities o
                JOIN projects p ON o.project_id = p.id
                WHERE o.impact_potential = 'high'
                AND date(o.first_seen_at) = ?
                ORDER BY o.first_seen_at DESC
                LIMIT 20
            """, (date,)).fetchall()
            
            # Generate markdown
            lines = [
                f"# AI Project Opportunities Report - {date}",
                "",
                "## Summary",
                "",
                f"- Early-burst projects detected: {len(projects)}",
                f"- High-impact opportunities identified: {len(opportunities)}",
                "",
                "---",
                "",
                "## Early-Burst Projects",
                ""
            ]
            
            for i, p in enumerate(projects, 1):
                tech = p['tech_layer'] or 'TBD'
                app = p['application'] or 'TBD'
                
                lines.extend([
                    f"### {i}. {p['name']}",
                    "",
                    f"**Score:** {p['overall_score']:.2f} (Velocity: {p['star_velocity_score']:.2f}, Activity: {p['activity_index_score']:.2f}, Novelty: {p['novelty_score']:.2f})",
                    "",
                    f"**Classification:** {tech} / {app}",
                    "",
                    f"**Stars:** {p['stars']} | **Language:** {p['language'] or 'N/A'}",
                    "",
                    f"**URL:** {p['url']}",
                    "",
                    f"**Description:** {p['description'] or 'No description'}",
                    "",
                    "---",
                    ""
                ])
            
            if opportunities:
                lines.extend([
                    "## Top Extension Opportunities",
                    ""
                ])
                
                for opp in opportunities:
                    lines.extend([
                        f"### {opp['title']}",
                        "",
                        f"**Project:** [{opp['project_name']}]({opp['project_url']})",
                        "",
                        f"**Type:** {opp['opportunity_type']} | **Impact:** {opp['impact_potential']} | **Difficulty:** {opp['difficulty']}",
                        "",
                        f"**Description:** {opp['description']}",
                        "",
                        f"**Key Insight:** {opp['key_insight'] or 'N/A'}",
                        "",
                        "---",
                        ""
                    ])
            
            # Write report
            report_path = os.path.join(
                os.path.dirname(self.db.db_path),
                'reports',
                f'{date}.md'
            )
            
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            
            print(f"Report generated: {report_path}")
            
        finally:
            conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', required=True, help="Report date (YYYY-MM-DD)")
    args = parser.parse_args()
    
    db = Database()
    generator = ReportGenerator(db)
    generator.generate(args.date)


if __name__ == '__main__':
    main()
```


## 7. 运行脚本

### 7.1 run.sh

```bash
#!/usr/bin/env bash
set -euo pipefail

FRAMEWORK_DIR="$(cd "$(dirname "$0")" && pwd)"
DB="$FRAMEWORK_DIR/data/framework.db"
DATE=$(date -u +%Y-%m-%d)

# Load environment
if [ -f "$FRAMEWORK_DIR/.env" ]; then
  set -a; source "$FRAMEWORK_DIR/.env"; set +a
fi

CLI_TOOL="${CLI_TOOL:-claude --dangerously-skip-permissions}"

echo "=== AI Project Opportunities Framework - $DATE ==="

# Git pull
echo "[0/5] git pull..."
git -C "$FRAMEWORK_DIR" pull --rebase 2>/dev/null || true

# Initialize DB
echo "[1/5] Initializing database..."
python3 "$FRAMEWORK_DIR/framework/stages/init_db.py"

# Stage 3: Semantic filtering (if pending projects)
FILTER_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM projects WHERE status='discovered';" 2>/dev/null || echo "0")

if [ "$FILTER_COUNT" -gt 0 ]; then
  echo "[2/5] Stage 3: Semantic filtering ($FILTER_COUNT projects)..."
  # TODO: Implement LLM-based filtering
  echo "  (Filtering to be implemented)"
else
  echo "[2/5] No projects to filter, skipping."
fi

# Stage 2: Schedule tasks
echo "[3/5] Scheduling tasks..."
python3 "$FRAMEWORK_DIR/framework/stages/schedule.py" --mode incremental

# Check pending tasks
PENDING=$(sqlite3 "$DB" "SELECT COUNT(*) FROM tasks WHERE task_date='$DATE' AND status='pending';" 2>/dev/null || echo "0")

if [ "$PENDING" -eq 0 ]; then
  echo "No pending tasks. Generating report..."
  python3 "$FRAMEWORK_DIR/framework/stages/report.py" --date "$DATE"
  exit 0
fi

echo "Pending tasks: $PENDING"

# Stage 4: LLM Analysis
echo "[4/5] LLM Analysis ($PENDING projects)..."
echo "  (LLM analysis to be implemented via prompts/ai_analyze.md)"

# Stage 5: Generate report
echo "[5/5] Generating report..."
python3 "$FRAMEWORK_DIR/framework/stages/report.py" --date "$DATE"

# Git push
echo "Pushing changes..."
git -C "$FRAMEWORK_DIR" add "$DB" "$FRAMEWORK_DIR/data/reports/" 2>/dev/null || true
git -C "$FRAMEWORK_DIR" diff --staged --quiet || \
  git -C "$FRAMEWORK_DIR" commit -m "feat: daily report $DATE"
git -C "$FRAMEWORK_DIR" push || true

echo "=== Complete ==="
echo "Report: $FRAMEWORK_DIR/data/reports/$DATE.md"
```

### 7.2 run_bulk.sh

```bash
#!/usr/bin/env bash
set -euo pipefail

FRAMEWORK_DIR="$(cd "$(dirname "$0")" && pwd)"
DB="$FRAMEWORK_DIR/data/framework.db"
BATCH_SIZE="${1:-20}"
DATE=$(date -u +%Y-%m-%d)

echo "=== Bulk Processing - $DATE (batch=$BATCH_SIZE) ==="

# Git pull
git -C "$FRAMEWORK_DIR" pull --rebase 2>/dev/null || true

# Initialize DB
python3 "$FRAMEWORK_DIR/framework/stages/init_db.py"

# Check pending bulk projects
PENDING_BULK=$(sqlite3 "$DB" "SELECT COUNT(*) FROM projects WHERE status='discovered';" 2>/dev/null || echo "0")

echo "Pending bulk projects: $PENDING_BULK"

if [ "$PENDING_BULK" -eq 0 ]; then
  echo "No bulk projects pending. Switch to run.sh for incremental mode."
  exit 0
fi

# Generate bulk tasks
python3 "$FRAMEWORK_DIR/framework/stages/schedule.py" --mode bulk --batch-size "$BATCH_SIZE"

# LLM Analysis (bulk mode)
BULK_TASKS=$(sqlite3 "$DB" "SELECT COUNT(*) FROM tasks WHERE task_date='$DATE' AND task_type='bulk' AND status='pending';" 2>/dev/null || echo "0")
echo "Bulk tasks to analyze: $BULK_TASKS"

# Stage 5: Generate report
python3 "$FRAMEWORK_DIR/framework/stages/report.py" --date "$DATE"

# Git push
git -C "$FRAMEWORK_DIR" add "$DB" "$FRAMEWORK_DIR/data/reports/" 2>/dev/null || true
git -C "$FRAMEWORK_DIR" diff --staged --quiet || \
  git -C "$FRAMEWORK_DIR" commit -m "feat: bulk analysis $DATE ($BULK_TASKS tasks)"
git -C "$FRAMEWORK_DIR" push || true

echo "=== Complete ==="
```


## 8. LLM 提示词模板

### 8.1 filter.md

**Purpose:** Semantic filtering of discovered projects

**Input:** Projects with status='discovered' from database

**Output:** Update projects table with:
- status: 'filtered_skip' or 'scheduled'
- tech_layer: one of 5 categories
- application: one of 6 categories
- filter_reason: explanation

```markdown
# Stage 3: Semantic Filtering for AI Projects

You are an AI project classifier. Process the pending projects below.

## 分类类别

**Tech Layer (choose one):**
- foundation_model: Base LLMs, multimodal models
- training_framework: Distributed training, fine-tuning
- inference_engine: Model serving, optimization, quantization
- ai_application: End-user AI applications
- ai_toolchain: Data processing, evaluation, deployment tools

**Application (choose one):**
- code_generation
- image_generation
- multimodal
- agent
- data_annotation
- model_evaluation

## 过滤规则

SKIP (status='filtered_skip') if ANY apply:
1. Name/description contains: awesome, tutorial, demo, examples, course, curated-list
2. No clear AI/ML focus (not LLM, not generative AI, not ML framework)
3. Empty repository or just documentation
4. Commercial product SDK only (no open-source core)

KEEP (status='scheduled') if ALL apply:
1. Clear AI focus
2. Active code repository
3. Solves a real problem

## 数据库操作

For each project, execute:

```sql
-- SKIP
UPDATE projects 
SET status='filtered_skip', filter_reason='<reason>'
WHERE id='<project_id>';

-- KEEP
UPDATE projects 
SET status='scheduled', tech_layer='<layer>', application='<app>', filter_reason='valid_ai_project'
WHERE id='<project_id>';
```

Use Python sqlite3 with parameterized queries. Commit after each project.

## 当前批次

Read from: SELECT * FROM projects WHERE status='discovered' LIMIT 50
```

### 8.2 ai_analyze.md

**Purpose:** Deep analysis of early-burst AI projects

**Input:** Single project with early-burst signals

**Output:** Insert into analyses and opportunities tables

```markdown
# Stage 4: Deep Analysis of AI Project

You are an AI industry analyst. Analyze this project deeply.

## 项目信息

Read from database:
- Project: SELECT * FROM projects WHERE id='<task_project_id>'
- Burst signals: SELECT * FROM early_burst_signals WHERE project_id='<id>' ORDER BY calculated_at DESC LIMIT 1

## 分析框架

### 1. Problem & Solution (problem_solved)
- What specific pain point does this address?
- Target users and use cases
- Painkiller vs vitamin assessment

### 2. Innovation Assessment (innovation_summary)
- Technical: New architecture, algorithm, training method?
- Product: New interaction pattern, UX innovation?
- Business: New monetization, distribution model?

### 3. Differentiation (differentiation)
- vs OpenAI/Anthropic/Google commercial offerings
- vs other open-source alternatives
- Sustainable moat analysis

### 4. Extension Opportunities

Identify 3-5 specific opportunities. For each:

```json
{
  "opportunity_type": "product|tech|market|integration|business_model",
  "title": "One-line description",
  "description": "Detailed what to build",
  "impact_potential": "high|medium|low",
  "difficulty": "high|medium|low",
  "time_horizon": "short|medium|long",
  "key_insight": "Why this opportunity exists now"
}
```

### 5. Market Timing (market_timing)
- Why is this the right time?
- Enabling technological shifts
- Key risks and challenges

### 6. Overall Score (overall_score)
Rate 1-10 based on:
- Innovation level
- Market opportunity size
- Execution quality
- Team/sustainability signals

## 输出

Insert into analyses table:
```sql
INSERT INTO analyses (project_id, analyzed_at, tech_layer, application,
  problem_solved, innovation_summary, differentiation, market_timing, 
  overall_score, analyzer_version)
VALUES (...)
```

Insert each opportunity:
```sql
INSERT INTO opportunities (project_id, source_analysis_date, 
  opportunity_type, title, description, impact_potential, difficulty,
  time_horizon, key_insight, first_seen_at, last_seen_at, status)
VALUES (...)
```

## 重要

- Be objective but insightful
- Focus on actionable extension opportunities
- Consider both technical and business angles
- Write in Chinese (zh) as configured
```


## 9. GitHub Actions 工作流

**File:** `.github/workflows/discover.yml`

```yaml
name: Daily Discover

on:
  schedule:
    - cron: '0 1 * * *'  # UTC 01:00 daily
  workflow_dispatch:

jobs:
  discover:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: pip install -r requirements.txt
      
      - name: Run discovery
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: python framework/stages/discover.py
      
      - name: Commit results
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/framework.db
          git diff --staged --quiet || git commit -m "chore: daily discover $(date +%Y-%m-%d)"
          git push
```

## 10. 错误处理策略

### 10.1 GitHub API Errors

| Error | Handling |
|-------|----------|
| 403 Rate Limit | Wait until X-RateLimit-Reset, max 1 hour |
| 429 Too Many Requests | Retry-After header, exponential backoff |
| 5xx Server Error | Retry 3x with 60s delay |
| Timeout | Retry with longer timeout |
| 404 Not Found | Skip repository, log warning |

### 10.2 Network Resilience

- All API calls wrapped in try/except
- Continue on individual source failure (don't fail entire pipeline)
- Log all errors to stderr for monitoring

### 10.3 Data Integrity

- Use database transactions for multi-step operations
- Rollback on error to prevent partial writes
- Unique constraints prevent duplicate entries

### 10.4 LLM Analysis Errors

- Timeout after 5 minutes per project
- Retry failed analysis up to 2 times
- Mark task as 'skipped' if analysis fails completely
- Continue pipeline, don't block on single project

## 11. 测试策略

### 11.1 Unit Tests

**File structure:**
```
tests/
├── __init__.py
├── test_config_loader.py
├── test_scoring_engine.py
├── test_scheduler.py
└── test_db.py
```

**Example test (test_scoring_engine.py):**
```python
import pytest
from framework.core.scoring_engine import ScoringEngine
from framework.core.config_loader import EarlyBurstConfig

def test_star_velocity_calculation():
    config = EarlyBurstConfig(
        enabled=True,
        min_score=0.65,
        metrics={
            'star_velocity': {'weight': 0.35, 'thresholds': {'weekly_growth_rate': 0.15, 'daily_absolute': 10}},
            'activity_index': {'weight': 0.25, 'thresholds': {}},
            'community_buzz': {'weight': 0.25, 'thresholds': {}},
            'novelty_signal': {'weight': 0.15, 'thresholds': {}}
        }
    )
    engine = ScoringEngine(config)
    
    # High growth
    score = engine.calculate_star_velocity(1000, 800, None)
    assert score > 0.8
    
    # No historical data
    score = engine.calculate_star_velocity(1000, None, None)
    assert score == 0.5
```

### 11.2 Integration Tests

- Mock GitHub API responses using responses library
- Test full pipeline with temporary database
- Test error conditions (rate limiting, timeouts)

### 11.3 Manual Testing Checklist

- [ ] `python framework/stages/init_db.py` creates all tables
- [ ] `python framework/stages/discover.py --dry-run` runs without errors
- [ ] `python framework/stages/schedule.py --mode bulk --dry-run` shows task count
- [ ] `./run.sh` executes full pipeline (with mocked LLM)
- [ ] Report generation produces valid Markdown
- [ ] GitHub Actions workflow runs successfully

## 12. 首次设置

### Step 1: Clone and Setup Environment

```bash
git clone <repo>
cd opensource-project-opportunities-framework
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add GITHUB_TOKEN
```

### Step 2: Initialize Database

```bash
python framework/stages/init_db.py
```

### Step 3: First Discovery Run

```bash
# Dry run to test
python framework/stages/discover.py --dry-run

# Actual run
python framework/stages/discover.py
```

### Step 4: Bulk Processing

```bash
# Run in batches until backlog cleared
./run_bulk.sh 20

# Check progress
sqlite3 data/framework.db "SELECT status, COUNT(*) FROM projects GROUP BY status;"
```

### Step 5: Switch to Daily Incremental

Once bulk queue cleared:
```bash
./run.sh
```

## 13. 未来扩展

| Feature | Priority | Description |
|---------|----------|-------------|
| Web Dashboard | Medium | Streamlit/FastAPI for browsing opportunities |
| Additional Categories | High | Web3, DevTools via config changes |
| Community Sources | Medium | Full HN/Reddit integration |
| Notifications | Low | Slack/Discord for high-score detections |
| Export Formats | Medium | JSON/CSV for external tools |
| Multi-LLM Support | Low | OpenAI, Gemini alternatives |

## 14. 变更日志

### v1.0 (2026-04-22)
- Initial design
- Core framework: config-driven, SQLite storage
- Early-burst scoring with 4 dimensions
- Star history sampling for velocity calculation
- Complete discover.py implementation with error handling

