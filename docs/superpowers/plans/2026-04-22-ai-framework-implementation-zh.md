# AI 框架实现计划

> **所需子技能：** 使用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans` 逐任务实现此计划。

**目标：** 实现完整的开源项目机会框架（opensource-project-opportunities-framework），支持 AI 类别。

**架构：** 配置驱动的 Python 框架，使用 SQLite 存储、早期爆发评分和 LLM 分析。

**技术栈：** Python 3.12、SQLite、PyYAML、Requests

---

## 阶段 1：项目结构与配置

### 任务 1：创建目录结构

**命令：**
```bash
mkdir -p opensource-project-opportunities-framework/{framework/{core,stages,prompts},data/reports,.github/workflows}
touch opensource-project-opportunities-framework/data/.gitkeep
touch opensource-project-opportunities-framework/data/reports/.gitkeep
touch opensource-project-opportunities-framework/framework/__init__.py
touch opensource-project-opportunities-framework/framework/core/__init__.py
touch opensource-project-opportunities-framework/framework/stages/__init__.py
touch opensource-project-opportunities-framework/framework/prompts/__init__.py
```

**验证：**
```bash
find opensource-project-opportunities-framework -type f -name "*.py" | head -10
```

**预期输出：**
```
opensource-project-opportunities-framework/framework/__init__.py
opensource-project-opportunities-framework/framework/core/__init__.py
opensource-project-opportunities-framework/framework/stages/__init__.py
opensource-project-opportunities-framework/framework/prompts/__init__.py
```

---

### 任务 2：创建 config.yaml

**文件：** `opensource-project-opportunities-framework/config.yaml`

```yaml
category:
  name: "ai"
  display_name: "AI 项目"
  version: "1.0.0"

dimensions:
  tech_layer:
    - id: foundation_model
      name: "基础模型"
    - id: training_framework
      name: "训练框架"
    - id: inference_engine
      name: "推理引擎"
    - id: ai_application
      name: "AI 应用"
    - id: ai_toolchain
      name: "AI 工具链"

  application:
    - id: code_generation
      name: "代码生成"
    - id: image_generation
      name: "图像生成"
    - id: multimodal
      name: "多模态"
    - id: agent
      name: "智能体"
    - id: data_annotation
      name: "数据标注"
    - id: model_evaluation
      name: "模型评估"

sources:
  github:
    topics:
      - "artificial-intelligence"
      - "machine-learning"
      - "deep-learning"
      - "llm"
      - "generative-ai"
      - "ai-agents"
    languages: ["Python", "TypeScript", "Rust", "Go"]
    star_range: [50, 50000]
  
  trending:
    languages: ["python", "typescript", "rust", "go"]
    periods: ["daily", "weekly"]
  
  ecosystems:
    - "huggingface"
    - "openai"
    - "langchain-ai"
    - "pytorch"

early_burst:
  enabled: true
  min_score: 0.65
  metrics:
    star_velocity:
      weight: 0.35
      thresholds:
        weekly_growth_rate: 0.15
        daily_absolute: 10
    activity_index:
      weight: 0.25
      thresholds:
        commit_frequency: 3
        pr_merge_rate: 0.3
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

filters:
  required:
    has_readme: true
    has_code: true
    min_contributors: 1
  skip_patterns:
    - "awesome"
    - "tutorial"
    - "demo"

scheduling:
  bulk:
    batch_size: 20
    max_per_day: 100
  incremental:
    max_per_day: 15

resilience:
  github_api:
    max_retries: 3
    retry_delay_seconds: 60
    rate_limit_wait_seconds: 3600
  llm_analysis:
    max_retries: 2
    timeout_seconds: 300
  star_history:
    sample_interval_days: 1
    min_samples_for_velocity: 3
```

---

### 任务 3：创建 requirements.txt

**文件：** `opensource-project-opportunities-framework/requirements.txt`

```
pyyaml>=6.0
requests>=2.31.0
python-dotenv>=1.0.0
```

**验证：**
```bash
cd opensource-project-opportunities-framework && pip install -r requirements.txt
```

---

### 任务 4：创建 .env.example

**文件：** `opensource-project-opportunities-framework/.env.example`

```bash
# 必需
GITHUB_TOKEN=your_github_personal_access_token_here

# 可选
CLI_TOOL="claude --dangerously-skip-permissions"
```

---

## 阶段 2：核心框架模块

### 任务 5：实现 config_loader.py

**文件：** `opensource-project-opportunities-framework/framework/core/config_loader.py`

    - "pytorch"

early_burst:
  enabled: true
  min_score: 0.65
  metrics:
    star_velocity:
      weight: 0.35
      thresholds:
        weekly_growth_rate: 0.15
        daily_absolute: 10
    activity_index:
      weight: 0.25
      thresholds:
        commit_frequency: 3
        pr_merge_rate: 0.3
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

filters:
  required:
    has_readme: true
    has_code: true
    min_contributors: 1
  skip_patterns:
    - "awesome"
    - "tutorial"
    - "demo"

scheduling:
  bulk:
    batch_size: 20
    max_per_day: 100
  incremental:
    max_per_day: 15

resilience:
  github_api:
    max_retries: 3
    retry_delay_seconds: 60
    rate_limit_wait_seconds: 3600
  llm_analysis:
    max_retries: 2
    timeout_seconds: 300
  star_history:
    sample_interval_days: 1
    min_samples_for_velocity: 3
```

---

### Task 3: Create requirements.txt

**File:** `opensource-project-opportunities-framework/requirements.txt`

```
pyyaml>=6.0
requests>=2.31.0
python-dotenv>=1.0.0
```

**Verify:**
```bash
cd opensource-project-opportunities-framework && pip install -r requirements.txt
```

---

### Task 4: Create .env.example

**File:** `opensource-project-opportunities-framework/.env.example`

```bash
# Required
GITHUB_TOKEN=your_github_personal_access_token_here

# Optional
CLI_TOOL="claude --dangerously-skip-permissions"
```

---

## Phase 2: Core Framework Modules

### Task 5: Implement config_loader.py

**File:** `opensource-project-opportunities-framework/framework/core/config_loader.py`

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
    
    def get_github_topics(self) -> List[str]:
        return self.load()['sources']['github']['topics']
    
    def get_star_range(self) -> tuple:
        return tuple(self.load()['sources']['github']['star_range'])
    
    def get_ecosystems(self) -> List[str]:
        return self.load()['sources']['ecosystems']
    
    def get_filters(self) -> Dict:
        return self.load()['filters']
    
    def get_scheduling_config(self) -> Dict:
        return self.load()['scheduling']
    
    def get_resilience_config(self) -> Dict:
        return self.load().get('resilience', {})
```

**Test:**
```python
python -c "
from framework.core.config_loader import ConfigLoader
c = ConfigLoader()
print('Category:', c.get_category().name)
print('Topics:', len(c.get_github_topics()))
print('Star range:', c.get_star_range())
"
```

---

### Task 6: Implement db.py

**File:** `opensource-project-opportunities-framework/framework/core/db.py`

```python
import sqlite3
import os
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone


class Database:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            db_path = os.path.join(base_dir, 'data', 'framework.db')
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    def get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def init_tables(self):
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
    
    def _create_projects(self, conn):
        conn.execute('''
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
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_p_status ON projects(status)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_p_tech ON projects(tech_layer)')
    
    def _create_star_history(self, conn):
        conn.execute('''
            CREATE TABLE IF NOT EXISTS star_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT REFERENCES projects(id),
                sampled_at TEXT,
                stars INTEGER,
                UNIQUE(project_id, sampled_at)
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_sh_proj ON star_history(project_id, sampled_at DESC)')
    
    def _create_early_burst_signals(self, conn):
        conn.execute('''
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
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_ebs_burst ON early_burst_signals(is_early_burst, overall_score DESC)')
    
    def _create_tasks(self, conn):
        conn.execute('''
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
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_tasks_date ON tasks(task_date, status)')
    
    def _create_analyses(self, conn):
        conn.execute('''
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
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_ana_proj ON analyses(project_id)')
    
    def _create_opportunities(self, conn):
        conn.execute('''
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
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_opp_proj ON opportunities(project_id)')
    
    def sample_star_count(self, project_id: str, stars: int):
        conn = self.get_conn()
        try:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute('''
                INSERT OR REPLACE INTO star_history (project_id, sampled_at, stars)
                VALUES (?, date(?), ?)
            ''', (project_id, now, stars))
            conn.commit()
        finally:
            conn.close()
    
    def get_project_star_history(self, project_id: str, days: int = 30) -> List[Dict]:
        conn = self.get_conn()
        try:
            cursor = conn.execute(f'''
                SELECT * FROM star_history 
                WHERE project_id = ? 
                AND sampled_at >= datetime("now", "-{days} days")
                ORDER BY sampled_at DESC
            ''', (project_id,))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
```

**Test:**
```python
python -c "
from framework.core.db import Database
db = Database()
db.init_tables()
print('Database initialized successfully')
"
```

---


## Phase 3: Scoring and Scheduling

### Task 7: Implement scoring_engine.py

**File:** `opensource-project-opportunities-framework/framework/core/scoring_engine.py`

```python
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from framework.core.config_loader import EarlyBurstConfig


class ScoringEngine:
    def __init__(self, config: EarlyBurstConfig):
        self.config = config
    
    def calculate_star_velocity(self, current: int, past_7d: Optional[int],
                                past_30d: Optional[int]) -> float:
        if past_7d is None or past_7d == 0 or current <= past_7d:
            return 0.5
        
        weekly_growth = (current - past_7d) / past_7d
        daily_absolute = (current - past_7d) / 7
        
        threshold = self.config.metrics['star_velocity']['thresholds']
        target_weekly = threshold['weekly_growth_rate']
        target_daily = threshold['daily_absolute']
        
        weekly_score = min(weekly_growth / target_weekly, 1.5)
        daily_score = min(daily_absolute / target_daily, 1.5)
        
        return min((weekly_score * 0.7 + daily_score * 0.3), 1.0)
    
    def calculate_activity_index(self, open_issues: int,
                                  commit_frequency: float,
                                  pr_merge_rate: Optional[float] = None) -> float:
        threshold = self.config.metrics['activity_index']['thresholds']
        score = 0.0
        
        if commit_frequency >= threshold['commit_frequency']:
            score += 0.4
        elif commit_frequency >= threshold['commit_frequency'] * 0.5:
            score += 0.2
        else:
            score += 0.1
        
        if pr_merge_rate is not None:
            if pr_merge_rate >= threshold['pr_merge_rate']:
                score += 0.3
            elif pr_merge_rate >= threshold['pr_merge_rate'] * 0.5:
                score += 0.15
        else:
            score += 0.15
        
        if open_issues >= 10:
            score += 0.3
        elif open_issues >= 3:
            score += 0.2
        elif open_issues > 0:
            score += 0.1
        
        return min(score, 1.0)
    
    def calculate_novelty(self, first_commit_at: Optional[str],
                          unique_contributors_weekly: int = 0) -> float:
        if first_commit_at is None:
            return 0.5
        
        try:
            first_commit = datetime.fromisoformat(first_commit_at.replace('Z', '+00:00'))
            months_old = (datetime.now(timezone.utc) - first_commit).days / 30
        except:
            return 0.5
        
        threshold = self.config.metrics['novelty_signal']['thresholds']
        max_months = threshold['first_commit_within_months'] * 2
        
        age_score = max(0, 1.0 - (months_old / max_months))
        
        contrib_threshold = threshold['unique_contributors_weekly']
        contrib_score = min(unique_contributors_weekly / contrib_threshold, 1.0) if contrib_threshold > 0 else 0
        
        return min(age_score * 0.6 + contrib_score * 0.4, 1.0)
    
    def calculate_overall(self, star_velocity: float, activity: float,
                          buzz: float, novelty: float) -> Dict[str, Any]:
        weights = self.config.metrics
        
        overall = (
            star_velocity * weights['star_velocity']['weight'] +
            activity * weights['activity_index']['weight'] +
            buzz * weights['community_buzz']['weight'] +
            novelty * weights['novelty_signal']['weight']
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

---

### Task 8: Implement scheduler.py

**File:** `opensource-project-opportunities-framework/framework/core/scheduler.py`

```python
import sqlite3
from datetime import datetime, timezone
from typing import List, Dict, Optional


class Scheduler:
    def __init__(self, db_path: str, config: Dict):
        self.db_path = db_path
        self.config = config
    
    def get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def generate_bulk_tasks(self, date: str, batch_size: int) -> int:
        conn = self.get_conn()
        try:
            cur = conn.execute('''
                SELECT p.id, COALESCE(e.overall_score, 0.5) as burst_score
                FROM projects p
                LEFT JOIN early_burst_signals e ON p.id = e.project_id
                WHERE p.status = 'discovered'
                AND p.id NOT IN (SELECT project_id FROM tasks WHERE task_type = 'bulk')
                ORDER BY burst_score DESC, p.stars DESC
                LIMIT ?
            ''', (batch_size,))
            
            count = 0
            for row in cur.fetchall():
                conn.execute('''
                    INSERT INTO tasks (project_id, task_date, task_type,
                        priority_score, trigger_reason, status, created_at)
                    VALUES (?, ?, 'bulk', ?, 'backlog_processing', 'pending', ?)
                ''', (row['id'], date, row['burst_score'],
                      datetime.now(timezone.utc).isoformat()))
                count += 1
            
            conn.commit()
            return count
        finally:
            conn.close()
    
    def generate_incremental_tasks(self, date: str, max_tasks: int) -> int:
        conn = self.get_conn()
        try:
            cur = conn.execute('''
                SELECT p.id, COALESCE(e.overall_score, 0.5) as burst_score
                FROM projects p
                LEFT JOIN early_burst_signals e ON p.id = e.project_id
                WHERE p.status = 'scheduled'
                AND p.id NOT IN (SELECT project_id FROM tasks WHERE task_date = ?)
                ORDER BY burst_score DESC
                LIMIT ?
            ''', (date, max_tasks))
            
            count = 0
            for row in cur.fetchall():
                conn.execute('''
                    INSERT INTO tasks (project_id, task_date, task_type,
                        priority_score, trigger_reason, status, created_at)
                    VALUES (?, ?, 'incremental', ?, 'new_discovery', 'pending', ?)
                ''', (row['id'], date, row['burst_score'],
                      datetime.now(timezone.utc).isoformat()))
                count += 1
            
            conn.commit()
            return count
        finally:
            conn.close()
```

---


## Phase 4: Pipeline Stages

### Task 9: Implement init_db.py

**File:** `opensource-project-opportunities-framework/framework/stages/init_db.py`

```python
#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from framework.core.db import Database


def main():
    db = Database()
    db.init_tables()
    print("Database initialized successfully.")


if __name__ == '__main__':
    main()
```

---

### Task 10: Implement discover.py

**File:** `opensource-project-opportunities-framework/framework/stages/discover.py`

This is a large file. Key components to implement:

1. **GitHubAPIError** - Custom exception for API errors
2. **DiscoverStage** class with methods:
   - `__init__` - Initialize with config and database
   - `_github_request` - API client with rate limiting and retries
   - `_should_skip_repo` - Filter rules application
   - `_upsert_project` - Database insert/update
   - `_sample_star_count` - Star history tracking
   - `_calculate_and_store_burst_score` - Scoring
   - `discover_topics` - Topic-based discovery
   - `discover_ecosystems` - Organization-based discovery
   - `run` - Main execution flow

**Key implementation details:**
- Use 2-second delay between search API calls (30/min limit)
- Use 0.5-second delay between core API calls
- Retry on 403/429 with exponential backoff
- Skip repos with <50 or >50000 stars
- Skip archived, stale (>180 days), or fork repos
- Sample star counts for all projects on each run
- Calculate burst scores after each discovery

**Full implementation:** See spec section 6.2 for complete code (~300 lines)

**Test command:**
```bash
cd opensource-project-opportunities-framework
export GITHUB_TOKEN=your_token_here
python framework/stages/discover.py --dry-run
```

---

### Task 11: Implement schedule.py

**File:** `opensource-project-opportunities-framework/framework/stages/schedule.py`

```python
#!/usr/bin/env python3
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
    args = parser.parse_args()
    
    config = ConfigLoader()
    db = Database()
    scheduler = Scheduler(db.db_path, config.get_scheduling_config())
    
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    if args.mode == 'bulk':
        count = scheduler.generate_bulk_tasks(today, args.batch_size)
    else:
        max_tasks = config.get_scheduling_config()['incremental']['max_per_day']
        count = scheduler.generate_incremental_tasks(today, max_tasks)
    
    print(f"Generated {count} tasks for {today}")


if __name__ == '__main__':
    main()
```

---

### Task 12: Implement report.py

**File:** `opensource-project-opportunities-framework/framework/stages/report.py`

```python
#!/usr/bin/env python3
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from framework.core.db import Database


class ReportGenerator:
    def __init__(self, db: Database):
        self.db = db
    
    def generate(self, date: str):
        conn = self.db.get_conn()
        try:
            # Get early-burst projects
            projects = conn.execute('''
                SELECT p.*, e.overall_score, e.star_velocity_score, 
                       e.activity_index_score, e.novelty_score
                FROM projects p
                JOIN early_burst_signals e ON p.id = e.project_id
                WHERE e.is_early_burst = 1
                AND date(e.calculated_at) = ?
                ORDER BY e.overall_score DESC
            ''', (date,)).fetchall()
            
            # Generate markdown
            lines = [
                f"# AI Project Opportunities Report - {date}",
                "",
                f"## Early-Burst Projects ({len(projects)})",
                ""
            ]
            
            for p in projects:
                tech = p['tech_layer'] or 'TBD'
                app = p['application'] or 'TBD'
                
                lines.extend([
                    f"### {p['name']}",
                    f"- **Score:** {p['overall_score']:.2f}",
                    f"- **Stars:** {p['stars']}",
                    f"- **URL:** {p['url']}",
                    f"- **Description:** {p['description'] or 'N/A'}",
                    ""
                ])
            
            # Write report
            report_path = os.path.join(
                os.path.dirname(self.db.db_path),
                'reports',
                f'{date}.md'
            )
            
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            with open(report_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            
            print(f"Report generated: {report_path}")
            
        finally:
            conn.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date', required=True)
    args = parser.parse_args()
    
    db = Database()
    generator = ReportGenerator(db)
    generator.generate(args.date)


if __name__ == '__main__':
    main()
```

---


## Phase 5: Run Scripts

### Task 13: Create run.sh

**File:** `opensource-project-opportunities-framework/run.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

FRAMEWORK_DIR="$(cd "$(dirname "$0")" && pwd)"
DB="$FRAMEWORK_DIR/data/framework.db"
DATE=$(date -u +%Y-%m-%d)

if [ -f "$FRAMEWORK_DIR/.env" ]; then
  set -a; source "$FRAMEWORK_DIR/.env"; set +a
fi

echo "=== AI Framework - $DATE ==="

git -C "$FRAMEWORK_DIR" pull --rebase 2>/dev/null || true

python3 "$FRAMEWORK_DIR/framework/stages/init_db.py"
python3 "$FRAMEWORK_DIR/framework/stages/schedule.py" --mode incremental

PENDING=$(sqlite3 "$DB" "SELECT COUNT(*) FROM tasks WHERE task_date='$DATE' AND status='pending';" 2>/dev/null || echo "0")

if [ "$PENDING" -gt 0 ]; then
  echo "Analyzing $PENDING projects..."
  # TODO: Implement LLM analysis via prompts/filter.md and prompts/ai_analyze.md
fi

python3 "$FRAMEWORK_DIR/framework/stages/report.py" --date "$DATE"

echo "=== Complete ==="
```

**Make executable:**
```bash
chmod +x opensource-project-opportunities-framework/run.sh
```

---

### Task 14: Create run_bulk.sh

**File:** `opensource-project-opportunities-framework/run_bulk.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail

FRAMEWORK_DIR="$(cd "$(dirname "$0")" && pwd)"
BATCH_SIZE="${1:-20}"
DATE=$(date -u +%Y-%m-%d)

echo "=== Bulk Processing - $DATE (batch=$BATCH_SIZE) ==="

git -C "$FRAMEWORK_DIR" pull --rebase 2>/dev/null || true
python3 "$FRAMEWORK_DIR/framework/stages/init_db.py"
python3 "$FRAMEWORK_DIR/framework/stages/schedule.py" --mode bulk --batch-size "$BATCH_SIZE"
python3 "$FRAMEWORK_DIR/framework/stages/report.py" --date "$DATE"

echo "=== Complete ==="
```

**Make executable:**
```bash
chmod +x opensource-project-opportunities-framework/run_bulk.sh
```

---

## Phase 6: Prompts and CI/CD

### Task 15: Create filter.md

**File:** `opensource-project-opportunities-framework/framework/prompts/filter.md`

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

For each project, execute SQL:

-- SKIP
UPDATE projects 
SET status='filtered_skip', filter_reason='<reason>'
WHERE id='<project_id>';

-- KEEP
UPDATE projects 
SET status='scheduled', tech_layer='<layer>', application='<app>'
WHERE id='<project_id>';

Use Python sqlite3. Commit after each project.

## Input

SELECT * FROM projects WHERE status='discovered' LIMIT 50
```

---

### Task 16: Create ai_analyze.md

**File:** `opensource-project-opportunities-framework/framework/prompts/ai_analyze.md`

```markdown
# Stage 4: Deep Analysis of AI Project

You are an AI industry analyst. Analyze this project deeply.

## Project Info

Query: SELECT * FROM projects WHERE id='<project_id>'
Query: SELECT * FROM early_burst_signals WHERE project_id='<id>' ORDER BY calculated_at DESC LIMIT 1

## Analysis Framework

### 1. Problem & Solution
- What specific pain point does this address?
- Target users and use cases
- Painkiller vs vitamin assessment

### 2. Innovation Assessment
- Technical: New architecture, algorithm, training method?
- Product: New interaction pattern, UX innovation?
- Business: New monetization, distribution model?

### 3. Differentiation
- vs OpenAI/Anthropic/Google commercial offerings
- vs other open-source alternatives
- Sustainable moat analysis

### 4. Extension Opportunities

Identify 3-5 opportunities. For each provide:
- opportunity_type: product|tech|market|integration|business_model
- title: One-line description
- description: What to build
- impact_potential: high|medium|low
- difficulty: high|medium|low
- time_horizon: short|medium|long
- key_insight: Why this opportunity exists now

### 5. Market Timing
- Why is this the right time?
- Enabling technological shifts
- Key risks and challenges

### 6. Overall Score
Rate 1-10 based on innovation, market size, execution, team

## Output

Insert into analyses table with all fields.
Insert each opportunity into opportunities table.
```

---

### Task 17: Create GitHub Actions Workflow

**File:** `opensource-project-opportunities-framework/.github/workflows/discover.yml`

```yaml
name: Daily Discover

on:
  schedule:
    - cron: '0 1 * * *'
  workflow_dispatch:

jobs:
  discover:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install -r requirements.txt
      - name: Discover
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: python framework/stages/discover.py
      - name: Commit
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/framework.db
          git diff --staged --quiet || git commit -m "chore: daily discover $(date +%Y-%m-%d)"
          git push
```

---


## Phase 7: Testing and Validation

### Task 18: Test Database Initialization

**Command:**
```bash
cd opensource-project-opportunities-framework
python framework/stages/init_db.py
sqlite3 data/framework.db ".schema"
```

**Expected output:** All 6 tables created:
- projects
- star_history
- early_burst_signals
- tasks
- analyses
- opportunities

---

### Task 19: Test Config Loading

**Command:**
```bash
python -c "
from framework.core.config_loader import ConfigLoader
c = ConfigLoader()
print('Category:', c.get_category().name)
print('Topics:', len(c.get_github_topics()))
print('Star range:', c.get_star_range())
"
```

**Expected:**
```
Category: ai
Topics: 6
Star range: (50, 50000)
```

---

### Task 20: Test Discovery (Dry Run)

**Command:**
```bash
export GITHUB_TOKEN=your_token_here
python framework/stages/discover.py --dry-run
```

**Expected:** Outputs discovered projects without writing to database.

---

## Execution Order Summary

| Phase | Tasks | Description | Est. Time |
|-------|-------|-------------|-----------|
| 1 | 1-4 | Directory structure, config, requirements, env | 15 min |
| 2 | 5-6 | config_loader.py, db.py | 30 min |
| 3 | 7-8 | scoring_engine.py, scheduler.py | 20 min |
| 4 | 9-12 | init_db.py, discover.py, schedule.py, report.py | 60 min |
| 5 | 13-14 | run.sh, run_bulk.sh | 10 min |
| 6 | 15-17 | filter.md, ai_analyze.md, GitHub Actions | 15 min |
| 7 | 18-20 | Testing and validation | 20 min |
| **Total** | **20 Tasks** | | **~2.5 hours** |

---

## Verification Checklist

Before considering implementation complete, verify:

- [ ] All 20 tasks completed
- [ ] All 6 database tables created
- [ ] config_loader loads YAML correctly
- [ ] db.py has all CRUD operations
- [ ] scoring_engine calculates all 4 metrics
- [ ] scheduler creates tasks correctly
- [ ] discover.py runs without errors (dry-run)
- [ ] discover.py handles rate limits gracefully
- [ ] report.py generates valid Markdown
- [ ] run.sh and run_bulk.sh are executable
- [ ] filter.md has complete prompt template
- [ ] ai_analyze.md has complete prompt template
- [ ] GitHub Actions workflow is valid YAML

---

## Notes

### discover.py Implementation

The discover.py file is intentionally large (~300 lines). Key methods:

1. `_github_request()` - API client with rate limiting
2. `_should_skip_repo()` - Filter rules
3. `_upsert_project()` - Database operations
4. `_sample_star_count()` - Star history
5. `_calculate_and_store_burst_score()` - Scoring
6. `discover_topics()` - Topic search
7. `discover_ecosystems()` - Org scanning
8. `run()` - Main orchestration

Reference the spec document section 6.2 for complete implementation if needed.

### LLM Analysis Integration

Tasks 15-16 provide the prompt templates. The actual LLM integration (calling Claude/OpenAI) is intentionally left as a future enhancement. The framework is designed to work with manual LLM analysis initially.

---

**Plan Complete and Fixed. Ready for Implementation.**

