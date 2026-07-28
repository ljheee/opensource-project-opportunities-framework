#!/usr/bin/env python3
"""
Validation Stage: Measure accuracy of early-burst predictions.

Tracks predictions made by the scoring engine and compares them against
actual outcomes to enable closed-loop improvement.
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from datetime import datetime, timezone

from framework.core.config_loader import ConfigLoader
from framework.core.db import Database


def _fn_threshold() -> float:
    """Fixed false-negative threshold: min_score x 8 x 0.5 (same basis as TP rule)."""
    try:
        min_score = ConfigLoader().get_early_burst_config().min_score
    except Exception:
        min_score = 0.65
    return min_score * 8 * 0.5


def _predicted_growth(overall_score) -> float:
    """Compute expected daily star growth from an overall score."""
    try:
        score = float(overall_score) if overall_score is not None else 0.0
    except (ValueError, TypeError):
        score = 0.0
    return max(score * 8, 1)


def record_new_predictions(db: Database, min_days_for_fn: int = 7):
    """Record predictions for projects first marked as early-burst."""
    conn = db.get_conn()
    try:
        # Find latest early-burst signal per project where is_early_burst=1
        # and no prediction_outcome record exists yet
        cur = conn.execute('''
            SELECT e.project_id, e.calculated_at, e.overall_score, p.stars,
                   e.star_velocity_score, e.activity_index_score,
                   e.community_buzz_score, e.novelty_score
            FROM early_burst_signals e
            JOIN projects p ON e.project_id = p.id
            JOIN (
                SELECT project_id, MAX(calculated_at) as latest_at
                FROM early_burst_signals
                WHERE is_early_burst = 1
                GROUP BY project_id
            ) latest ON e.project_id = latest.project_id
                     AND e.calculated_at = latest.latest_at
            WHERE e.is_early_burst = 1
              AND NOT EXISTS (
                  SELECT 1 FROM prediction_outcomes po
                  WHERE po.project_id = e.project_id
              )
        ''')

        recorded = 0
        for row in cur.fetchall():
            predicted_growth = _predicted_growth(row['overall_score'])
            conn.execute('''
                INSERT INTO prediction_outcomes
                (project_id, predicted_at, stars_at_prediction,
                 overall_score_at_prediction,
                 star_velocity_at_pred, activity_index_at_pred,
                 community_buzz_at_pred, novelty_at_pred,
                 growth_rate_predicted,
                 checked_at, outcome)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, date('now'), 'pending')
            ''', (row['project_id'], row['calculated_at'],
                  row['stars'], row['overall_score'],
                  row['star_velocity_score'], row['activity_index_score'],
                  row['community_buzz_score'], row['novelty_score'],
                  predicted_growth))
            recorded += 1

        # FN candidates: trending-source projects that did NOT reach early-burst,
        # old enough to evaluate, and never recorded before.
        fn_threshold = _fn_threshold()
        fn_cur = conn.execute('''
            SELECT p.id as project_id, p.first_seen_at, p.stars,
                   e.overall_score, e.calculated_at
            FROM projects p
            JOIN (
                SELECT project_id, overall_score, calculated_at, is_early_burst,
                       ROW_NUMBER() OVER (PARTITION BY project_id ORDER BY calculated_at DESC) as rn
                FROM early_burst_signals
            ) e ON p.id = e.project_id AND e.rn = 1
            WHERE p.source = 'trending'
              AND e.is_early_burst IS NOT 1
              AND julianday('now') - julianday(p.first_seen_at) >= ?
              AND NOT EXISTS (
                  SELECT 1 FROM prediction_outcomes po WHERE po.project_id = p.id
              )
        ''', (min_days_for_fn,))

        fn_recorded = 0
        for row in fn_cur.fetchall():
            baseline = conn.execute('''
                SELECT stars FROM star_history
                WHERE project_id = ? AND sampled_at <= date(?)
                ORDER BY sampled_at DESC LIMIT 1
            ''', (row['project_id'], row['first_seen_at'])).fetchone()
            baseline_stars = baseline['stars'] if baseline else row['stars']
            # 无星史样本时基线是当前 stars，checked_at 记首次发现日（spec §2.4-2）
            if baseline:
                checked_at = datetime.now(timezone.utc).strftime('%Y-%m-%d')
            else:
                checked_at = str(row['first_seen_at'])[:10]
            conn.execute('''
                INSERT INTO prediction_outcomes
                (project_id, predicted_at, stars_at_prediction,
                 overall_score_at_prediction,
                 star_velocity_at_pred, activity_index_at_pred,
                 community_buzz_at_pred, novelty_at_pred,
                 growth_rate_predicted,
                 checked_at, outcome)
                VALUES (?, ?, ?, ?, NULL, NULL, NULL, NULL, ?, ?, 'pending')
            ''', (row['project_id'], row['first_seen_at'],
                  baseline_stars, row['overall_score'],
                  fn_threshold, checked_at))
            fn_recorded += 1
        print(f"Recorded {fn_recorded} new FN candidates")

        conn.commit()
        print(f"Recorded {recorded} new predictions")
        return recorded
    finally:
        conn.close()


def check_pending_outcomes(db: Database, min_days: int = 7):
    """Update pending predictions that have aged enough to evaluate."""
    conn = db.get_conn()
    try:
        # Find pending predictions older than min_days
        cur = conn.execute('''
            SELECT po.id, po.project_id, po.stars_at_prediction,
                   po.overall_score_at_prediction, po.predicted_at,
                   po.growth_rate_predicted, po.star_velocity_at_pred,
                   p.stars as stars_now,
                   CAST(julianday('now') - julianday(po.predicted_at) AS INTEGER) as days_elapsed
            FROM prediction_outcomes po
            JOIN projects p ON po.project_id = p.id
            WHERE po.outcome = 'pending'
              AND julianday('now') - julianday(po.predicted_at) >= ?
        ''', (min_days,))

        updated = 0
        for row in cur.fetchall():
            try:
                stars_then = int(row['stars_at_prediction']) if row['stars_at_prediction'] is not None else 0
            except (ValueError, TypeError):
                stars_then = 0
            try:
                stars_now = int(row['stars_now']) if row['stars_now'] is not None else 0
            except (ValueError, TypeError):
                stars_now = 0
            try:
                days_elapsed = int(row['days_elapsed']) if row['days_elapsed'] is not None else min_days
            except (ValueError, TypeError):
                days_elapsed = min_days
            days = max(days_elapsed, 1)

            # Actual growth rate per day
            try:
                actual_growth = (stars_now - stars_then) / days
            except (TypeError, ZeroDivisionError):
                actual_growth = 0.0

            # Predicted trajectory: overall_score maps roughly to expected growth
            try:
                pred_growth = float(row['growth_rate_predicted']) if row['growth_rate_predicted'] is not None else None
            except (ValueError, TypeError):
                pred_growth = None
            predicted_growth = pred_growth if pred_growth is not None else _predicted_growth(row['overall_score_at_prediction'])

            # 方向在记录时已固化：FN 候选行的组件列全为 NULL（Step 2 插入的）。
            # 不要用 score vs 当前 min_score 重判——reweight 可能已调整阈值，
            # 会把存量 TP 候选行错误重分类。
            is_tp_candidate = row['star_velocity_at_pred'] is not None

            if is_tp_candidate:
                # 原有 TP 候选逻辑（保持不变）
                if stars_now <= stars_then:
                    outcome = 'false_positive'
                elif actual_growth >= predicted_growth * 0.5:
                    outcome = 'true_positive'
                else:
                    outcome = 'false_positive'
            else:
                # FN 候选：实际增速超过记录时固化的阈值（growth_rate_predicted）
                # = 我们漏掉的爆发；不读 live min_score，避免 reweight 后阈值漂移。
                if actual_growth >= predicted_growth:
                    outcome = 'false_negative'
                else:
                    outcome = 'true_negative'

            conn.execute('''
                UPDATE prediction_outcomes
                SET checked_at = date('now'),
                    stars_now = ?,
                    growth_rate_actual = ?,
                    growth_rate_predicted = ?,
                    outcome = ?
                WHERE id = ?
            ''', (stars_now, actual_growth, predicted_growth, outcome, row['id']))
            updated += 1

        conn.commit()
        print(f"Updated {updated} pending outcomes")
        return updated
    finally:
        conn.close()


def print_metrics(db: Database):
    """Print validation metrics to stdout."""
    conn = db.get_conn()
    try:
        try:
            total = int(conn.execute(
                "SELECT COUNT(*) FROM prediction_outcomes WHERE outcome IN ('true_positive', 'false_positive')"
            ).fetchone()[0] or 0)
        except (ValueError, TypeError):
            total = 0
        try:
            tp = int(conn.execute(
                "SELECT COUNT(*) FROM prediction_outcomes WHERE outcome = 'true_positive'"
            ).fetchone()[0] or 0)
        except (ValueError, TypeError):
            tp = 0
        try:
            fp = int(conn.execute(
                "SELECT COUNT(*) FROM prediction_outcomes WHERE outcome = 'false_positive'"
            ).fetchone()[0] or 0)
        except (ValueError, TypeError):
            fp = 0
        try:
            pending = int(conn.execute(
                "SELECT COUNT(*) FROM prediction_outcomes WHERE outcome = 'pending'"
            ).fetchone()[0] or 0)
        except (ValueError, TypeError):
            pending = 0
        try:
            fn = int(conn.execute(
                "SELECT COUNT(*) FROM prediction_outcomes WHERE outcome = 'false_negative'"
            ).fetchone()[0] or 0)
        except (ValueError, TypeError):
            fn = 0
        try:
            tn = int(conn.execute(
                "SELECT COUNT(*) FROM prediction_outcomes WHERE outcome = 'true_negative'"
            ).fetchone()[0] or 0)
        except (ValueError, TypeError):
            tn = 0

        print("\n=== Prediction Validation Metrics ===")
        print(f"Total evaluated: {total}  (TP: {tp}, FP: {fp})")
        print(f"Pending (too recent): {pending}")

        if total > 0:
            precision = tp / total
            print(f"Precision (7d+ horizon): {precision:.2%}")

            try:
                avg_tp = float(conn.execute('''
                    SELECT AVG(growth_rate_actual) FROM prediction_outcomes
                    WHERE outcome = 'true_positive'
                ''').fetchone()[0] or 0)
            except (ValueError, TypeError):
                avg_tp = 0.0
            try:
                avg_fp = float(conn.execute('''
                    SELECT AVG(growth_rate_actual) FROM prediction_outcomes
                    WHERE outcome = 'false_positive'
                ''').fetchone()[0] or 0)
            except (ValueError, TypeError):
                avg_fp = 0.0

            print(f"Avg actual growth — TP: {avg_tp:.1f} stars/day, FP: {avg_fp:.1f} stars/day")

        if fn + tn > 0 or tp > 0:
            tp_trending = int(conn.execute('''
                SELECT COUNT(*) FROM prediction_outcomes po
                JOIN projects p ON po.project_id = p.id
                WHERE po.outcome = 'true_positive' AND p.source = 'trending'
            ''').fetchone()[0] or 0)
            print(f"Recall candidates — FN (missed bursts): {fn}, TN: {tn}")
            if tp_trending + fn > 0:
                print(f"Recall (trending-source): {tp_trending / (tp_trending + fn):.2%}")

        # Score bucket calibration
        print("\n--- Score Bucket Calibration ---")
        buckets = conn.execute('''
            SELECT
                CASE
                    WHEN overall_score_at_prediction >= 0.8 THEN '0.8+'
                    WHEN overall_score_at_prediction >= 0.7 THEN '0.7-0.8'
                    WHEN overall_score_at_prediction >= 0.65 THEN '0.65-0.7'
                    ELSE '<0.65'
                END as bucket,
                COUNT(*) as total,
                SUM(CASE WHEN outcome = 'true_positive' THEN 1 ELSE 0 END) as tp_count
            FROM prediction_outcomes
            WHERE outcome IN ('true_positive', 'false_positive')
            GROUP BY bucket
            ORDER BY MIN(overall_score_at_prediction) DESC
        ''').fetchall()

        for b in buckets:
            try:
                b_total = int(b['total']) if b['total'] is not None else 0
            except (ValueError, TypeError):
                b_total = 0
            try:
                b_tp = int(b['tp_count']) if b['tp_count'] is not None else 0
            except (ValueError, TypeError):
                b_tp = 0
            prec = b_tp / b_total if b_total > 0 else 0
            print(f"  {b['bucket']}: {b_total} eval, precision {prec:.0%}")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Validate early-burst predictions")
    parser.add_argument('--min-days', type=int, default=7,
                        help="Minimum days before evaluating a prediction")
    parser.add_argument('--metrics-only', action='store_true',
                        help="Only print metrics, do not update")
    args = parser.parse_args()

    if args.min_days < 0:
        print("ERROR: min-days must be non-negative")
        sys.exit(1)

    db = Database()

    if not args.metrics_only:
        record_new_predictions(db)
        check_pending_outcomes(db, min_days=args.min_days)

    print_metrics(db)


if __name__ == '__main__':
    main()
