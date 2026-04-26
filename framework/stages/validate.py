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

from framework.core.db import Database


def _predicted_growth(overall_score: float) -> float:
    """Compute expected daily star growth from an overall score."""
    return max((overall_score or 0) * 8, 1)


def record_new_predictions(db: Database):
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
                   po.growth_rate_predicted,
                   p.stars as stars_now,
                   CAST(julianday('now') - julianday(po.predicted_at) AS INTEGER) as days_elapsed
            FROM prediction_outcomes po
            JOIN projects p ON po.project_id = p.id
            WHERE po.outcome = 'pending'
              AND julianday('now') - julianday(po.predicted_at) >= ?
        ''', (min_days,))

        updated = 0
        for row in cur.fetchall():
            stars_then = row['stars_at_prediction'] or 0
            stars_now = row['stars_now'] or 0
            days = max(row['days_elapsed'] or min_days, 1)

            # Actual growth rate per day
            try:
                actual_growth = (stars_now - stars_then) / days
            except (TypeError, ZeroDivisionError):
                actual_growth = 0.0

            # Predicted trajectory: overall_score maps roughly to expected growth
            predicted_growth = row['growth_rate_predicted'] or _predicted_growth(row['overall_score_at_prediction'])

            # Fast-path: star decline or zero growth is always false positive
            if stars_now <= stars_then:
                outcome = 'false_positive'
            elif actual_growth >= predicted_growth * 0.5:
                outcome = 'true_positive'
            else:
                outcome = 'false_positive'

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
        total = conn.execute(
            "SELECT COUNT(*) FROM prediction_outcomes WHERE outcome != 'pending'"
        ).fetchone()[0]

        tp = conn.execute(
            "SELECT COUNT(*) FROM prediction_outcomes WHERE outcome = 'true_positive'"
        ).fetchone()[0]

        fp = conn.execute(
            "SELECT COUNT(*) FROM prediction_outcomes WHERE outcome = 'false_positive'"
        ).fetchone()[0]

        pending = conn.execute(
            "SELECT COUNT(*) FROM prediction_outcomes WHERE outcome = 'pending'"
        ).fetchone()[0]

        print("\n=== Prediction Validation Metrics ===")
        print(f"Total evaluated: {total}  (TP: {tp}, FP: {fp})")
        print(f"Pending (too recent): {pending}")

        if total > 0:
            precision = tp / total
            print(f"Precision (7d+ horizon): {precision:.2%}")

            avg_tp = conn.execute('''
                SELECT AVG(growth_rate_actual) FROM prediction_outcomes
                WHERE outcome = 'true_positive'
            ''').fetchone()[0] or 0

            avg_fp = conn.execute('''
                SELECT AVG(growth_rate_actual) FROM prediction_outcomes
                WHERE outcome = 'false_positive'
            ''').fetchone()[0] or 0

            print(f"Avg actual growth — TP: {avg_tp:.1f} stars/day, FP: {avg_fp:.1f} stars/day")

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
            WHERE outcome != 'pending'
            GROUP BY bucket
            ORDER BY MIN(overall_score_at_prediction) DESC
        ''').fetchall()

        for b in buckets:
            prec = b['tp_count'] / b['total'] if b['total'] > 0 else 0
            print(f"  {b['bucket']}: {b['total']} eval, precision {prec:.0%}")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Validate early-burst predictions")
    parser.add_argument('--min-days', type=int, default=7,
                        help="Minimum days before evaluating a prediction")
    parser.add_argument('--metrics-only', action='store_true',
                        help="Only print metrics, do not update")
    args = parser.parse_args()

    db = Database()

    if not args.metrics_only:
        record_new_predictions(db)
        check_pending_outcomes(db, min_days=args.min_days)

    print_metrics(db)


if __name__ == '__main__':
    main()
