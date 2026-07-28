import sqlite3
import os
from typing import Optional, List, Dict
from datetime import datetime, timezone


class Database:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            db_path = os.path.join(base_dir, 'data', 'framework.db')
        self.db_path = db_path
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    def get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _add_column_if_missing(self, conn, table, column, col_def):
        """Add a column if it doesn't already exist."""
        cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
        if column not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
            print(f"DB migration: added {table}.{column}")

    def _migrate_projects(self, conn):
        """Migrate projects table: add missing columns."""
        self._add_column_if_missing(conn, 'projects', 'first_commit_at', 'TEXT')
        self._add_column_if_missing(conn, 'projects', 'last_commit_at', 'TEXT')
        self._add_column_if_missing(conn, 'projects', 'topics', 'TEXT')
        self._add_column_if_missing(conn, 'projects', 'description', 'TEXT')
        self._add_column_if_missing(conn, 'projects', 'tech_layer', 'TEXT')
        self._add_column_if_missing(conn, 'projects', 'application', 'TEXT')
        self._add_column_if_missing(conn, 'projects', 'category', 'TEXT')
        self._add_column_if_missing(conn, 'projects', 'source', 'TEXT')
        self._add_column_if_missing(conn, 'projects', 'status', 'TEXT')
        self._add_column_if_missing(conn, 'projects', 'filter_reason', 'TEXT')
        self._add_column_if_missing(conn, 'projects', 'first_seen_at', 'TEXT')
        self._add_column_if_missing(conn, 'projects', 'last_fetched_at', 'TEXT')
        self._add_column_if_missing(conn, 'projects', 'contributor_count', 'INTEGER')
        self._add_column_if_missing(conn, 'projects', 'prev_stars', 'INTEGER')
        self._add_column_if_missing(conn, 'projects', 'prev_open_issues', 'INTEGER')

    def _migrate_tasks(self, conn):
        """Migrate tasks table: add missing columns."""
        if not self._table_exists(conn, 'tasks'):
            return
        self._add_column_if_missing(conn, 'tasks', 'early_burst_score', 'REAL')
        self._add_column_if_missing(conn, 'tasks', 'opportunities_found', 'INTEGER')

    def _migrate_prediction_outcomes(self, conn):
        """Migrate prediction_outcomes table: add component score columns."""
        if not self._table_exists(conn, 'prediction_outcomes'):
            return
        self._add_column_if_missing(conn, 'prediction_outcomes', 'star_velocity_at_pred', 'REAL')
        self._add_column_if_missing(conn, 'prediction_outcomes', 'activity_index_at_pred', 'REAL')
        self._add_column_if_missing(conn, 'prediction_outcomes', 'community_buzz_at_pred', 'REAL')
        self._add_column_if_missing(conn, 'prediction_outcomes', 'novelty_at_pred', 'REAL')
        self._add_column_if_missing(conn, 'prediction_outcomes', 'growth_rate_predicted', 'REAL')

    def _migrate_analyses(self, conn):
        """Migrate analyses table: add missing columns and CHECK constraint via table rebuild."""
        # Crash recovery first: handle interrupted migration from previous run
        analyses_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='analyses'"
        ).fetchone() is not None
        new_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='analyses_new'"
        ).fetchone() is not None

        if not analyses_exists and new_exists:
            conn.execute("ALTER TABLE analyses_new RENAME TO analyses")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ana_proj ON analyses(project_id)")
            print("DB migration: recovered interrupted migration (analyses_new -> analyses)")
            return

        if analyses_exists and new_exists:
            conn.execute("DROP TABLE analyses_new")

        if not analyses_exists:
            # Table will be created by _create_analyses; nothing to migrate
            return

        # Add missing columns via ALTER TABLE (for existing schema before rebuild)
        self._add_column_if_missing(conn, 'analyses', 'application', 'TEXT')
        self._add_column_if_missing(conn, 'analyses', 'problem_solved', 'TEXT')
        self._add_column_if_missing(conn, 'analyses', 'innovation_summary', 'TEXT')
        self._add_column_if_missing(conn, 'analyses', 'differentiation', 'TEXT')
        self._add_column_if_missing(conn, 'analyses', 'market_timing', 'TEXT')
        self._add_column_if_missing(conn, 'analyses', 'overall_score', 'INTEGER')
        self._add_column_if_missing(conn, 'analyses', 'ecosystem_position', 'TEXT')
        self._add_column_if_missing(conn, 'analyses', 'commercialization_path', 'TEXT')
        self._add_column_if_missing(conn, 'analyses', 'analyzer_version', 'TEXT')

        has_check = False
        cursor = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='analyses'"
        ).fetchone()
        if cursor and cursor['sql']:
            has_check = 'CHECK(overall_score BETWEEN 1 AND 10)' in cursor['sql']

        if has_check:
            return

        conn.execute("DROP TABLE IF EXISTS analyses_new")
        conn.execute("""
            CREATE TABLE analyses_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT REFERENCES projects(id),
                analyzed_at TEXT,
                tech_layer TEXT,
                application TEXT,
                problem_solved TEXT,
                innovation_summary TEXT,
                differentiation TEXT,
                market_timing TEXT,
                ecosystem_position TEXT,
                commercialization_path TEXT,
                overall_score INTEGER CHECK(overall_score BETWEEN 1 AND 10),
                analyzer_version TEXT
            )
        """)
        conn.execute("""
            INSERT INTO analyses_new (
                id, project_id, analyzed_at, tech_layer, application,
                problem_solved, innovation_summary, differentiation,
                market_timing, ecosystem_position, commercialization_path,
                overall_score, analyzer_version
            )
            SELECT
                id, project_id, analyzed_at, tech_layer, application,
                problem_solved, innovation_summary, differentiation,
                market_timing, ecosystem_position, commercialization_path,
                CASE WHEN CAST(COALESCE(overall_score, 5) AS INTEGER) < 1 THEN 1
                     WHEN CAST(COALESCE(overall_score, 5) AS INTEGER) > 10 THEN 10
                     ELSE CAST(COALESCE(overall_score, 5) AS INTEGER) END,
                analyzer_version
            FROM analyses
        """)
        conn.execute("DROP TABLE analyses")
        conn.execute("ALTER TABLE analyses_new RENAME TO analyses")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ana_proj ON analyses(project_id)")
        print("DB migration: analyses table rebuilt with CHECK(overall_score BETWEEN 1 AND 10)")

    def init_tables(self):
        conn = self.get_conn()
        try:
            self._create_projects(conn)
            self._create_star_history(conn)
            self._create_early_burst_signals(conn)
            self._create_tasks(conn)
            self._migrate_tasks(conn)
            self._migrate_projects(conn)
            self._migrate_analyses(conn)
            self._create_analyses(conn)
            self._create_opportunities(conn)
            self._create_prediction_outcomes(conn)
            self._migrate_prediction_outcomes(conn)
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
                description TEXT,
                tech_layer TEXT,
                application TEXT,
                category TEXT,
                source TEXT,
                status TEXT DEFAULT 'discovered',
                filter_reason TEXT,
                first_seen_at TEXT,
                last_fetched_at TEXT,
                contributor_count INTEGER,
                prev_stars INTEGER,
                prev_open_issues INTEGER
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
                opportunities_found INTEGER,
                UNIQUE(project_id, task_date, task_type)
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
                ecosystem_position TEXT,
                commercialization_path TEXT,
                overall_score INTEGER CHECK(overall_score BETWEEN 1 AND 10),
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

    def _create_prediction_outcomes(self, conn):
        conn.execute('''
            CREATE TABLE IF NOT EXISTS prediction_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT REFERENCES projects(id),
                predicted_at TEXT,
                stars_at_prediction INTEGER,
                overall_score_at_prediction REAL,
                star_velocity_at_pred REAL,
                activity_index_at_pred REAL,
                community_buzz_at_pred REAL,
                novelty_at_pred REAL,
                growth_rate_predicted REAL,
                checked_at TEXT,
                stars_now INTEGER,
                growth_rate_actual REAL,
                outcome TEXT
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_pred_proj ON prediction_outcomes(project_id)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_pred_outcome ON prediction_outcomes(outcome)')

    def _table_exists(self, conn, table_name: str) -> bool:
        """Check if a table exists in the database."""
        result = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        ).fetchone()
        return result is not None

    def repair_analyzing_status(self):
        """Reset projects and tasks stuck after crash."""
        conn = self.get_conn()
        try:
            if not self._table_exists(conn, 'tasks'):
                return
            # Reset tasks stuck in 'running' back to 'pending'
            conn.execute("""
                UPDATE tasks SET status='pending', started_at=NULL
                WHERE status='running'
            """)
            # Bump old pending tasks to today so they remain schedulable,
            # but only if no today's task already exists (avoid UNIQUE violation)
            conn.execute("""
                UPDATE tasks
                SET task_date=date('now')
                WHERE status='pending' AND task_date < date('now')
                  AND NOT EXISTS (
                      SELECT 1 FROM tasks t2
                      WHERE t2.project_id = tasks.project_id
                        AND t2.task_type = tasks.task_type
                        AND t2.task_date = date('now')
                  )
            """)
            if not self._table_exists(conn, 'projects'):
                conn.commit()
                return
            # Priority 1: projects with completed tasks and no pending/running → reset to active
            conn.execute("""
                UPDATE projects SET status='active'
                WHERE status='analyzing'
                  AND EXISTS (SELECT 1 FROM tasks t WHERE t.project_id = projects.id AND t.status='done')
                  AND NOT EXISTS (
                      SELECT 1 FROM tasks t
                      WHERE t.project_id = projects.id
                        AND t.status IN ('pending','running')
                  )
            """)
            # Priority 2: projects with pending/running tasks
            # → reset to scheduled so they can be rescheduled/re-picked
            conn.execute("""
                UPDATE projects SET status='scheduled'
                WHERE status='analyzing'
                  AND id IN (
                      SELECT DISTINCT project_id FROM tasks
                      WHERE status IN ('pending','running')
                  )
            """)
            # Priority 3: remaining → reset to discovered
            # Exclude projects already handled by Priority 1 or 2
            conn.execute("""
                UPDATE projects SET status='discovered'
                WHERE status='analyzing'
                  AND NOT EXISTS (
                      SELECT 1 FROM tasks t
                      WHERE t.project_id = projects.id
                        AND t.status IN ('pending','running')
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM tasks t WHERE t.project_id = projects.id AND t.status='done'
                  )
            """)
            conn.commit()
        finally:
            conn.close()

    def repair_orphan_records(self):
        """Fix records referencing non-existent projects."""
        conn = self.get_conn()
        try:
            if self._table_exists(conn, 'tasks') and self._table_exists(conn, 'projects'):
                conn.execute("""
                    DELETE FROM tasks
                    WHERE NOT EXISTS (
                        SELECT 1 FROM projects WHERE projects.id = tasks.project_id
                    )
                """)
            if self._table_exists(conn, 'analyses') and self._table_exists(conn, 'projects'):
                conn.execute("""
                    DELETE FROM analyses
                    WHERE NOT EXISTS (
                        SELECT 1 FROM projects WHERE projects.id = analyses.project_id
                    )
                """)
            if self._table_exists(conn, 'opportunities') and self._table_exists(conn, 'projects'):
                conn.execute("""
                    DELETE FROM opportunities
                    WHERE NOT EXISTS (
                        SELECT 1 FROM projects WHERE projects.id = opportunities.project_id
                    )
                """)
            if self._table_exists(conn, 'star_history') and self._table_exists(conn, 'projects'):
                conn.execute("""
                    DELETE FROM star_history
                    WHERE NOT EXISTS (
                        SELECT 1 FROM projects WHERE projects.id = star_history.project_id
                    )
                """)
            if self._table_exists(conn, 'early_burst_signals') and self._table_exists(conn, 'projects'):
                conn.execute("""
                    DELETE FROM early_burst_signals
                    WHERE NOT EXISTS (
                        SELECT 1 FROM projects WHERE projects.id = early_burst_signals.project_id
                    )
                """)
            if self._table_exists(conn, 'prediction_outcomes') and self._table_exists(conn, 'projects'):
                conn.execute("""
                    DELETE FROM prediction_outcomes
                    WHERE NOT EXISTS (
                        SELECT 1 FROM projects WHERE projects.id = prediction_outcomes.project_id
                    )
                """)
            conn.commit()
        finally:
            conn.close()

    def sample_star_count(self, project_id: str, stars: int, conn=None):
        should_close = conn is None
        conn = conn or self.get_conn()
        try:
            now = datetime.now(timezone.utc).isoformat()
            conn.execute('''
                INSERT INTO star_history (project_id, sampled_at, stars)
                VALUES (?, date(?), ?)
                ON CONFLICT(project_id, sampled_at) DO UPDATE SET
                    stars = excluded.stars
            ''', (project_id, now, stars))
            if should_close:
                conn.commit()
        finally:
            if should_close:
                conn.close()

    def get_project_star_history(self, project_id: str, days: int = 30) -> List[Dict]:
        conn = self.get_conn()
        try:
            cursor = conn.execute('''
                SELECT * FROM star_history
                WHERE project_id = ?
                AND sampled_at >= date('now', '-' || ? || ' days')
                ORDER BY sampled_at DESC
            ''', (project_id, days))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_peer_projects(self, project_id: str, tech_layer: str,
                          application: str, limit: int = 5,
                          conn=None) -> List[Dict]:
        """Find peer projects in the same category for comparison."""
        should_close = conn is None
        conn = conn or self.get_conn()
        try:
            cursor = conn.execute('''
                SELECT id, name, url, stars, created_at,
                       tech_layer, application
                FROM projects
                WHERE id != ?
                  AND tech_layer = ?
                  AND application = ?
                  AND status IN ('active', 'scheduled')
                ORDER BY CAST(stars AS INTEGER) DESC
                LIMIT ?
            ''', (project_id, tech_layer or 'ai_application',
                  application or 'multimodal', limit))
            return [dict(row) for row in cursor.fetchall()]
        finally:
            if should_close:
                conn.close()
