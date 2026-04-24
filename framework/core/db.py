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
            cursor = conn.execute('''
                SELECT * FROM star_history
                WHERE project_id = ?
                AND sampled_at >= datetime('now', '-' || ? || ' days')
                ORDER BY sampled_at DESC
            ''', (project_id, days))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()
