import sqlite3
from datetime import datetime, timezone
from enum import Enum
from typing import List, Dict, Optional


class TaskType(Enum):
    BULK = "bulk"
    INCREMENTAL = "incremental"
    RE_EVALUATE = "re_evaluate"


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
        if max_tasks <= 0:
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
                ORDER BY burst_score DESC, p.stars DESC
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

    def mark_task_running(self, task_id: int, conn=None):
        """Mark a task as running."""
        should_close = conn is None
        conn = conn or self.get_conn()
        try:
            cursor = conn.execute("""
                UPDATE tasks SET status = 'running', started_at = ?
                WHERE id = ?
            """, (datetime.now(timezone.utc).isoformat(), task_id))
            if cursor.rowcount == 0:
                raise ValueError(f"Task {task_id} not found or already running")
            if should_close:
                conn.commit()
        finally:
            if should_close:
                conn.close()

    def mark_task_done(self, task_id: int, opportunities_found: int = 0, conn=None):
        """Mark a task as completed."""
        should_close = conn is None
        conn = conn or self.get_conn()
        try:
            cursor = conn.execute("""
                UPDATE tasks SET status = 'done', finished_at = ?, opportunities_found = ?
                WHERE id = ?
            """, (datetime.now(timezone.utc).isoformat(), opportunities_found, task_id))
            if cursor.rowcount == 0:
                raise ValueError(f"Task {task_id} not found")
            if should_close:
                conn.commit()
        finally:
            if should_close:
                conn.close()

    def mark_task_failed(self, task_id: int, error_message: str = None, conn=None):
        """Mark a task as failed."""
        should_close = conn is None
        conn = conn or self.get_conn()
        try:
            cursor = conn.execute("""
                UPDATE tasks SET status = 'failed', finished_at = ?, trigger_reason = ?
                WHERE id = ?
            """, (datetime.now(timezone.utc).isoformat(), error_message or 'analysis_failed', task_id))
            if cursor.rowcount == 0:
                raise ValueError(f"Task {task_id} not found")
            if should_close:
                conn.commit()
        finally:
            if should_close:
                conn.close()
