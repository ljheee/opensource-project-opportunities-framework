# Open Source Project Opportunities Framework - AI Category Design Spec

> **Version:** v1.1  
> **Date:** 2026-04-22  
> **Goal:** Build a configurable framework to discover early-burst AI projects, analyze their innovation, and identify extension opportunities.

---

## 1. Overview

### 1.1 Problem Statement

The AI open-source landscape evolves rapidly. Projects can go from unknown to trending in days. Identifying promising projects in their **early-burst phase** (before they become saturated) provides significant value for:
- Contributors looking for high-impact opportunities
- Investors tracking emerging trends
- Developers seeking innovative tools

### 1.2 Solution Approach

A **configuration-driven framework** that:
1. Discovers AI projects from multiple sources (GitHub, HN, Reddit)
2. Calculates an "early-burst score" based on velocity, activity, buzz, and novelty
3. Uses LLM to deeply analyze high-potential projects
4. Identifies extension opportunities with impact assessment

### 1.3 Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Config-driven (not plugin) | Simpler for single-category focus; can evolve to plugins later |
| SQLite + Markdown | Matches reference pipeline; proven for this use case |
| Separate bulk/incremental scripts | Clear operational model: bulk for backlog, incremental for daily |
| 2D classification (tech × app) | AI projects span many dimensions; rigid categories fail |

---


## 2. Directory Structure

```
opensource-project-opportunities-framework/
├── config.yaml                      # Main configuration
├── requirements.txt                 # Python dependencies
│
├── framework/                       # Framework core code
│   ├── __init__.py
│   ├── core/                        # Core modules
│   │   ├── __init__.py
│   │   ├── config_loader.py        # Parse config.yaml
│   │   ├── db.py                   # Database operations
│   │   ├── scheduler.py            # Task scheduling logic
│   │   └── scoring_engine.py       # Early-burst score calculation
│   │
│   ├── stages/                      # Pipeline stages
│   │   ├── __init__.py
│   │   ├── init_db.py              # Database initialization
│   │   ├── discover.py             # Multi-source discovery
│   │   ├── schedule.py             # Task generation
│   │   └── report.py               # Markdown report generation
│   │
│   └── prompts/                     # LLM prompt templates
│       ├── filter.md               # Stage 3: Semantic filtering
│       └── ai_analyze.md           # Stage 4: Deep analysis
│
├── data/                            # Data directory
│   ├── .gitkeep
│   ├── framework.db                # SQLite database
│   └── reports/                    # Daily markdown reports
│       └── .gitkeep
│
├── .github/
│   └── workflows/
│       └── discover.yml            # GitHub Actions workflow
│
├── run.sh                          # Daily incremental runner
├── run_bulk.sh                     # Backlog bulk processing
└── .env.example                    # Environment template
```


## 3. Configuration (config.yaml)

```yaml
# Category Configuration
category:
  name: "ai"
  display_name: "AI Projects"
  version: "1.0.0"

# Two-dimensional classification
dimensions:
  tech_layer:
    - id: foundation_model
      name: "Foundation Model"
      description: "Base LLMs, multimodal models, domain-specific models"
    
    - id: training_framework
      name: "Training Framework"
      description: "Distributed training, fine-tuning, RL frameworks"
    
    - id: inference_engine
      name: "Inference Engine"
      description: "Model serving, optimization, quantization"
    
    - id: ai_application
      name: "AI Application"
      description: "End-user applications built on AI"
    
    - id: ai_toolchain
      name: "AI Toolchain"
      description: "Data processing, evaluation, deployment tools"

  application:
    - id: code_generation
      name: "Code Generation"
    
    - id: image_generation
      name: "Image Generation"
    
    - id: multimodal
      name: "Multimodal"
    
    - id: agent
      name: "Agent / Autonomous System"
    
    - id: data_annotation
      name: "Data Annotation & Processing"
    
    - id: model_evaluation
      name: "Model Evaluation & Safety"

# Discovery Sources
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
      enabled: false              # Requires local run with API key
      keywords: ["show hn", "llm", "ai model", "local llm", "ai agent"]
      min_score: 30
    
    reddit:
      enabled: false              # Requires local run with API key
      subreddits: ["MachineLearning", "LocalLLaMA", "artificial", "OpenAI"]
      min_upvotes: 15

# Early-Burst Detection
early_burst:
  enabled: true
  min_score: 0.65                    # Threshold to flag as early-burst
  
  metrics:
    star_velocity:
      weight: 0.35
      thresholds:
        weekly_growth_rate: 0.15     # 15% weekly growth
        daily_absolute: 10           # At least 10 stars/day
    
    activity_index:
      weight: 0.25
      thresholds:
        issue_response_hours: 48
        pr_merge_rate: 0.3
        commit_frequency: 3          # Commits per week
    
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

# Filtering Rules
filters:
  required:
    has_readme: true
    has_code: true
    min_contributors: 1              # AI allows solo projects
  
  skip_patterns:
    - "awesome"
    - "awesome-list"
    - "curated-list"
    - "tutorial"
    - "course"
    - "examples"
    - "playground"
    - "demo"

# LLM Analysis
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

# Scheduling
scheduling:
  bulk:
    batch_size: 20
    max_per_day: 100
  
  incremental:
    max_per_day: 15
  
  re_evaluate:
    interval_days: 7

# Reporting
report:
  format: "markdown"
  language: "zh"
  sections:
    - summary
    - early_burst_projects
    - top_opportunities
    - trends

# Error Handling & Resilience
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
    sample_interval_days: 1          # How often to sample star counts
    min_samples_for_velocity: 3      # Min samples needed for velocity calc
```


## 4. Database Schema

### 4.1 projects

```sql
CREATE TABLE projects (
    id TEXT PRIMARY KEY,                    -- "owner/repo"
    name TEXT,
    url TEXT,
    language TEXT,
    
    -- Metrics (current)
    stars INTEGER,
    open_issues INTEGER,
    forks INTEGER,
    
    -- Temporal
    created_at TEXT,                        -- Repo creation
    first_commit_at TEXT,
    last_commit_at TEXT,
    
    -- Categorization
    topics TEXT,                            -- JSON array
    tech_layer TEXT,                        -- From dimensions
    application TEXT,                       -- From dimensions
    
    -- Discovery metadata
    category TEXT,                          -- "ai"
    source TEXT,                            -- github_topic/trending/ecosystem/hn/reddit
    
    -- Filtering
    status TEXT,                            -- discovered/filtered_skip/scheduled/active
    filter_reason TEXT,
    
    -- Tracking
    first_seen_at TEXT,
    last_fetched_at TEXT,
    contributor_count INTEGER
);

CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_projects_tech_layer ON projects(tech_layer);
CREATE INDEX idx_projects_application ON projects(application);
CREATE INDEX idx_projects_stars ON projects(stars DESC);
```

### 4.2 star_history (NEW - for velocity calculation)

GitHub API does not provide historical star counts. We sample daily to build history.

```sql
CREATE TABLE star_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES projects(id),
    sampled_at TEXT,                        -- ISO8601 timestamp
    stars INTEGER,                          -- Star count at sample time
    
    UNIQUE(project_id, sampled_at)
);

CREATE INDEX idx_star_history_project ON star_history(project_id, sampled_at DESC);
CREATE INDEX idx_star_history_sampled ON star_history(sampled_at);
```

**Sampling Strategy:**
- Every time `discover.py` runs, it samples current star count for all active projects
- Velocity calculated from samples: 7-day = (current - sample_from_7d_ago), 30-day similarly
- If insufficient samples exist, velocity score is set to 0.5 (neutral)

### 4.3 early_burst_signals

```sql
CREATE TABLE early_burst_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES projects(id),
    calculated_at TEXT,
    
    -- Component scores (0-1)
    star_velocity_score REAL,
    activity_index_score REAL,
    community_buzz_score REAL,
    novelty_score REAL,
    
    -- Overall
    overall_score REAL,
    is_early_burst BOOLEAN,
    
    -- Raw data for debugging
    signals_json TEXT,                      -- Original metrics
    
    UNIQUE(project_id, calculated_at)
);

CREATE INDEX idx_ebs_early_burst ON early_burst_signals(is_early_burst, overall_score DESC);
```


### 4.4 tasks

```sql
CREATE TABLE tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES projects(id),
    task_date TEXT,                         -- YYYY-MM-DD
    
    -- Task type
    task_type TEXT,                         -- bulk/incremental/re_evaluate
    priority_score REAL,                    -- For ordering
    trigger_reason TEXT,
    
    -- Status
    status TEXT,                            -- pending/running/done/skipped
    created_at TEXT,
    started_at TEXT,
    finished_at TEXT,
    
    -- Results summary
    early_burst_score REAL,
    opportunities_found INTEGER
);

CREATE INDEX idx_tasks_date_status ON tasks(task_date, status);
CREATE INDEX idx_tasks_project ON tasks(project_id);
```

### 4.5 analyses

```sql
CREATE TABLE analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES projects(id),
    analyzed_at TEXT,
    
    -- Classification (confirmed by LLM)
    tech_layer TEXT,
    application TEXT,
    
    -- Analysis content
    problem_solved TEXT,                    -- What problem does it solve
    innovation_summary TEXT,                -- Core innovation
    differentiation TEXT,                   -- vs competitors
    market_timing TEXT,                     -- Why now
    
    -- Scoring
    overall_score INTEGER,                  -- 1-10
    
    -- Metadata
    analyzer_version TEXT                   -- Prompt/template version
);

CREATE INDEX idx_analyses_project ON analyses(project_id);
```

### 4.6 opportunities

```sql
CREATE TABLE opportunities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES projects(id),
    
    -- Source tracking
    source_analysis_date TEXT,
    
    -- Opportunity details
    opportunity_type TEXT,                  -- product/tech/market/integration/business_model
    title TEXT,
    description TEXT,
    
    -- Assessment
    impact_potential TEXT,                  -- high/medium/low
    difficulty TEXT,
    time_horizon TEXT,                      -- short/medium/long
    
    -- Insight
    key_insight TEXT,
    evidence TEXT,                          -- JSON: supporting facts
    
    -- Lifecycle
    first_seen_at TEXT,
    last_seen_at TEXT,
    status TEXT DEFAULT 'open'              -- open/claimed/stale/realized
);

CREATE INDEX idx_opportunities_project ON opportunities(project_id);
CREATE INDEX idx_opportunities_type ON opportunities(opportunity_type);
```


## 5. Core Modules

### 5.1 config_loader.py

**Responsibility:** Load and validate config.yaml

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


### 5.2 scoring_engine.py

**Responsibility:** Calculate early-burst scores from metrics

```python
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from framework.core.config_loader import EarlyBurstConfig

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

**Responsibility:** Database operations and connection management

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

**Responsibility:** Generate and manage analysis tasks

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


## 6. Pipeline Stages

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


## 7. Run Scripts

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


## 8. LLM Prompt Templates

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

## Classification Categories

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

## Filtering Rules

SKIP (status='filtered_skip') if ANY apply:
1. Name/description contains: awesome, tutorial, demo, examples, course, curated-list
2. No clear AI/ML focus (not LLM, not generative AI, not ML framework)
3. Empty repository or just documentation
4. Commercial product SDK only (no open-source core)

KEEP (status='scheduled') if ALL apply:
1. Clear AI focus
2. Active code repository
3. Solves a real problem

## Database Operations

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

## Current Batch

Read from: SELECT * FROM projects WHERE status='discovered' LIMIT 50
```

### 8.2 ai_analyze.md

**Purpose:** Deep analysis of early-burst AI projects

**Input:** Single project with early-burst signals

**Output:** Insert into analyses and opportunities tables

```markdown
# Stage 4: Deep Analysis of AI Project

You are an AI industry analyst. Analyze this project deeply.

## Project Info

Read from database:
- Project: SELECT * FROM projects WHERE id='<task_project_id>'
- Burst signals: SELECT * FROM early_burst_signals WHERE project_id='<id>' ORDER BY calculated_at DESC LIMIT 1

## Analysis Framework

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

## Output

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

## Important

- Be objective but insightful
- Focus on actionable extension opportunities
- Consider both technical and business angles
- Write in Chinese (zh) as configured
```


## 9. GitHub Actions Workflow

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

## 10. Error Handling Strategy

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

## 11. Testing Strategy

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

## 12. First-Time Setup

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

## 13. Future Extensions

| Feature | Priority | Description |
|---------|----------|-------------|
| Web Dashboard | Medium | Streamlit/FastAPI for browsing opportunities |
| Additional Categories | High | Web3, DevTools via config changes |
| Community Sources | Medium | Full HN/Reddit integration |
| Notifications | Low | Slack/Discord for high-score detections |
| Export Formats | Medium | JSON/CSV for external tools |
| Multi-LLM Support | Low | OpenAI, Gemini alternatives |

## 14. Changelog

### v1.0 (2026-04-22)
- Initial design
- Core framework: config-driven, SQLite storage
- Early-burst scoring with 4 dimensions
- Star history sampling for velocity calculation
- Complete discover.py implementation with error handling

