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
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def generate_bulk_tasks(self, date: str, batch_size: int) -> int:
        if batch_size <= 0:
            return 0
        conn = self.get_conn()
        try:
            cur = conn.execute('''
                SELECT p.id, COALESCE(e.overall_score, 0.5) as burst_score
                FROM projects p
                LEFT JOIN (
                    SELECT project_id, overall_score,
                           ROW_NUMBER() OVER (PARTITION BY project_id ORDER BY calculated_at DESC) as rn
                    FROM early_burst_signals
                ) e ON p.id = e.project_id AND e.rn = 1
                WHERE p.status = 'scheduled'
                AND NOT EXISTS (
                    SELECT 1 FROM tasks t
                    WHERE t.project_id = p.id
                    AND t.task_type = 'bulk'
                    AND t.status = 'done'
                )
                AND NOT EXISTS (
                    SELECT 1 FROM tasks t
                    WHERE t.project_id = p.id
                    AND t.task_type = 'bulk'
                    AND t.status IN ('pending', 'running')
                )
                AND NOT EXISTS (
                    SELECT 1 FROM tasks t
                    WHERE t.project_id = p.id
                    AND t.status IN ('pending', 'running')
                )
                ORDER BY burst_score DESC, p.stars DESC, p.id ASC
                LIMIT ?
            ''', (batch_size,))

            count = 0
            for row in cur.fetchall():
                try:
                    conn.execute('''
                        INSERT INTO tasks (project_id, task_date, task_type,
                            priority_score, trigger_reason, status, created_at)
                        VALUES (?, ?, 'bulk', ?, 'backlog_processing', 'pending', ?)
                    ''', (row['id'], date, row['burst_score'],
                          datetime.now(timezone.utc).isoformat()))
                    count += 1
                except sqlite3.IntegrityError:
                    # Another process inserted the same task concurrently
                    continue

            conn.commit()
            return count
        finally:
            conn.close()

    def generate_incremental_tasks(self, date: str, max_tasks: int) -> int:
        if max_tasks <= 0:
            return 0
        inc = (self.config or {}).get('incremental') or {}
        try:
            star_threshold = float(inc.get('star_change_threshold', 0.05))
        except (ValueError, TypeError):
            star_threshold = 0.05
        try:
            recent_commit_days = int(inc.get('recent_commit_days', 3))
        except (ValueError, TypeError):
            recent_commit_days = 3
        try:
            cooldown_days = int(inc.get('min_reanalyze_days', 7))
        except (ValueError, TypeError):
            cooldown_days = 7

        conn = self.get_conn()
        try:
            cur = conn.execute('''
                SELECT p.id, COALESCE(e.overall_score, 0.5) as burst_score
                FROM projects p
                LEFT JOIN (
                    SELECT project_id, overall_score,
                           ROW_NUMBER() OVER (PARTITION BY project_id ORDER BY calculated_at DESC) as rn
                    FROM early_burst_signals
                ) e ON p.id = e.project_id AND e.rn = 1
                WHERE p.status IN ('scheduled', 'active')
                AND NOT EXISTS (
                    SELECT 1 FROM tasks t
                    WHERE t.project_id = p.id
                    AND t.task_type = 'incremental'
                    AND t.task_date = ?
                )
                AND NOT EXISTS (
                    SELECT 1 FROM tasks t
                    WHERE t.project_id = p.id
                    AND t.status IN ('pending', 'running')
                )
                AND (
                    -- Never analyzed: always eligible
                    NOT EXISTS (SELECT 1 FROM tasks t WHERE t.project_id = p.id AND t.status = 'done')
                    OR (
                        -- Cooldown elapsed since last analysis.
                        -- datetime() normalizes ISO 'T...+00:00' to SQLite 'YYYY-MM-DD HH:MM:SS';
                        -- COALESCE prevents starvation when a done task exists but analyses rows are gone.
                        COALESCE(
                            datetime((SELECT MAX(a.analyzed_at) FROM analyses a WHERE a.project_id = p.id)),
                            '1970-01-01'
                        ) <= datetime('now', '-' || ? || ' days')
                        AND (
                            -- 7-day star growth >= threshold (unknown history -> not satisfied)
                            (
                                SELECT CASE WHEN h.old_stars > 0
                                       THEN (CAST(p.stars AS REAL) - h.old_stars) / h.old_stars
                                       ELSE 0 END
                                FROM (
                                    SELECT stars as old_stars FROM star_history
                                    WHERE project_id = p.id
                                      AND sampled_at <= date('now', '-7 days')
                                    ORDER BY sampled_at DESC LIMIT 1
                                ) h
                            ) >= ?
                            OR datetime(p.last_commit_at) >= datetime('now', '-' || ? || ' days')
                        )
                    )
                )
                ORDER BY burst_score DESC, p.stars DESC, p.id ASC
                LIMIT ?
            ''', (date, cooldown_days, star_threshold, recent_commit_days, max_tasks))

            count = 0
            for row in cur.fetchall():
                try:
                    conn.execute('''
                        INSERT INTO tasks (project_id, task_date, task_type,
                            priority_score, trigger_reason, status, created_at)
                        VALUES (?, ?, 'incremental', ?, 'new_discovery', 'pending', ?)
                    ''', (row['id'], date, row['burst_score'],
                          datetime.now(timezone.utc).isoformat()))
                    count += 1
                except sqlite3.IntegrityError:
                    # Another process inserted the same task concurrently
                    continue

            conn.commit()
            return count
        finally:
            conn.close()

    def mark_task_running(self, task_id: int, conn=None):
        """Mark a task as running (only if currently pending)."""
        should_close = conn is None
        conn = conn or self.get_conn()
        try:
            cursor = conn.execute("""
                UPDATE tasks SET status = 'running', started_at = ?
                WHERE id = ? AND status = 'pending'
            """, (datetime.now(timezone.utc).isoformat(), task_id))
            if cursor.rowcount == 0:
                raise ValueError(f"Task {task_id} not found or not pending")
            if should_close:
                conn.commit()
        finally:
            if should_close:
                conn.close()

    def mark_task_done(self, task_id: int, opportunities_found: int = 0, conn=None):
        """Mark a task as completed (only if currently running)."""
        should_close = conn is None
        conn = conn or self.get_conn()
        try:
            cursor = conn.execute("""
                UPDATE tasks SET status = 'done', finished_at = ?, opportunities_found = ?
                WHERE id = ? AND status = 'running'
            """, (datetime.now(timezone.utc).isoformat(), opportunities_found, task_id))
            if cursor.rowcount == 0:
                raise ValueError(f"Task {task_id} not found or not running")
            if should_close:
                conn.commit()
        finally:
            if should_close:
                conn.close()

    def mark_task_failed(self, task_id: int, error_message: str = None, conn=None):
        """Mark a task as failed (only if currently running)."""
        should_close = conn is None
        conn = conn or self.get_conn()
        try:
            cursor = conn.execute("""
                UPDATE tasks SET status = 'failed', finished_at = ?, trigger_reason = ?
                WHERE id = ? AND status = 'running'
            """, (datetime.now(timezone.utc).isoformat(), error_message or 'analysis_failed', task_id))
            if cursor.rowcount == 0:
                raise ValueError(f"Task {task_id} not found or not running")
            if should_close:
                conn.commit()
        finally:
            if should_close:
                conn.close()
