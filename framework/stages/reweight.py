#!/usr/bin/env python3
"""
Weight Auto-Tuning Stage: Learn from validation outcomes and propose weight adjustments.

Usage:
    python framework/stages/reweight.py --dry-run    # Show proposal without changing config
    python framework/stages/reweight.py --apply      # Apply proposed changes to config.yaml
"""
import os
import sys
import argparse
import shutil
import yaml
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from framework.core.db import Database

COMPONENTS = ['star_velocity', 'activity_index', 'community_buzz', 'novelty_signal']
COMPONENT_COLS = {
    'star_velocity': 'star_velocity_at_pred',
    'activity_index': 'activity_index_at_pred',
    'community_buzz': 'community_buzz_at_pred',
    'novelty_signal': 'novelty_at_pred',
}


def _correlation(x, y):
    """Pearson correlation coefficient (Python 3.9 compat)."""
    n = len(x)
    if n < 2 or len(y) != n:
        return None
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    num = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    den_x = sum((xi - mean_x) ** 2 for xi in x) ** 0.5
    den_y = sum((yi - mean_y) ** 2 for yi in y) ** 0.5
    if den_x == 0 or den_y == 0:
        return None
    return num / (den_x * den_y)


# Adjustment constraints
MIN_WEIGHT = 0.05
MAX_WEIGHT = 0.60
MAX_ADJUSTMENT_RATIO = 0.20
MIN_SAMPLES = 20


def _to_float(val, default=0.0):
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def fetch_outcomes(db: Database):
    """Fetch all non-pending prediction outcomes with component scores."""
    conn = db.get_conn()
    try:
        cursor = conn.execute('''
            SELECT project_id, overall_score_at_prediction,
                   star_velocity_at_pred, activity_index_at_pred,
                   community_buzz_at_pred, novelty_at_pred,
                   outcome
            FROM prediction_outcomes
            WHERE outcome IN ('true_positive', 'false_positive')
        ''')
        rows = []
        for row in cursor.fetchall():
            r = dict(row)
            r['overall_score_at_prediction'] = _to_float(r.get('overall_score_at_prediction'))
            r['star_velocity_at_pred'] = _to_float(r.get('star_velocity_at_pred'))
            r['activity_index_at_pred'] = _to_float(r.get('activity_index_at_pred'))
            r['community_buzz_at_pred'] = _to_float(r.get('community_buzz_at_pred'))
            r['novelty_at_pred'] = _to_float(r.get('novelty_at_pred'))
            rows.append(r)
        return rows
    finally:
        conn.close()


def compute_overall_precision(rows):
    tp = sum(1 for r in rows if r['outcome'] == 'true_positive')
    total = len(rows)
    return tp / total if total > 0 else 0.0, tp, total - tp


def compute_bucket_calibration(rows):
    """Compute precision per score bucket."""
    buckets = {}
    for r in rows:
        score = r['overall_score_at_prediction'] or 0
        if score >= 0.8:
            key = '0.8+'
        elif score >= 0.7:
            key = '0.7-0.8'
        elif score >= 0.65:
            key = '0.65-0.7'
        else:
            key = '<0.65'
        if key not in buckets:
            buckets[key] = {'total': 0, 'tp': 0}
        buckets[key]['total'] += 1
        if r['outcome'] == 'true_positive':
            buckets[key]['tp'] += 1

    result = []
    for key in ['0.8+', '0.7-0.8', '0.65-0.7', '<0.65']:
        if key in buckets:
            b = buckets[key]
            result.append({
                'bucket': key,
                'total': b['total'],
                'precision': b['tp'] / b['total'] if b['total'] > 0 else 0.0
            })
    return result


def compute_component_correlation(rows):
    """Compare TP vs FP average scores per component."""
    tp_rows = [r for r in rows if r['outcome'] == 'true_positive']
    fp_rows = [r for r in rows if r['outcome'] == 'false_positive']

    if not tp_rows or not fp_rows:
        return {}

    result = {}
    for comp in COMPONENTS:
        col = COMPONENT_COLS[comp]
        tp_vals = [r[col] or 0 for r in tp_rows]
        fp_vals = [r[col] or 0 for r in fp_rows]
        tp_avg = sum(tp_vals) / len(tp_vals)
        fp_avg = sum(fp_vals) / len(fp_vals)

        # Try Pearson correlation if we have enough data
        all_vals = [r[col] or 0 for r in rows]
        labels = [1 if r['outcome'] == 'true_positive' else 0 for r in rows]
        try:
            corr = _correlation(all_vals, labels)
        except Exception:
            corr = None

        result[comp] = {
            'tp_avg': tp_avg,
            'fp_avg': fp_avg,
            'discriminative_power': tp_avg - fp_avg,
            'correlation': corr,
        }
    return result


def compute_threshold_optimization(rows):
    """Scan thresholds to find precision/coverage trade-offs."""
    thresholds = [0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
    results = []
    total = len(rows)
    for t in thresholds:
        subset = [r for r in rows if (r['overall_score_at_prediction'] or 0) >= t]
        tp = sum(1 for r in subset if r['outcome'] == 'true_positive')
        fp = sum(1 for r in subset if r['outcome'] == 'false_positive')
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        coverage = len(subset) / total if total > 0 else 0.0
        results.append({
            'threshold': t,
            'precision': precision,
            'coverage': coverage,
            'count': len(subset),
        })
    return results


def propose_new_weights(current_weights: dict, comp_corr: dict):
    """Propose new weights based on discriminative power.

    Falls back to current weights if comp_corr is empty or incomplete.
    """
    if not comp_corr or any(comp not in comp_corr for comp in COMPONENTS):
        return dict(current_weights)

    # Base new weights on discriminative_power (shifted to be all positive)
    powers = {comp: comp_corr[comp]['discriminative_power'] for comp in COMPONENTS}
    min_power = min(powers.values())

    # Shift so minimum is slightly above zero
    shifted = {comp: max(powers[comp] - min_power + 0.01, 0.01) for comp in COMPONENTS}
    total_shifted = sum(shifted.values())

    target_weights = {}
    for comp in COMPONENTS:
        target_weights[comp] = shifted[comp] / total_shifted

    # Apply max change constraint
    new_weights = {}
    for comp in COMPONENTS:
        cw = current_weights.get(comp, 0.25)
        tw = target_weights[comp]
        max_change = cw * MAX_ADJUSTMENT_RATIO
        delta = tw - cw
        if abs(delta) > max_change:
            delta = max_change if delta > 0 else -max_change
        new_weights[comp] = cw + delta

    # Enforce bounds
    for comp in COMPONENTS:
        new_weights[comp] = max(MIN_WEIGHT, min(MAX_WEIGHT, new_weights[comp]))

    # Renormalize to sum = 1.0
    total = sum(new_weights.values())
    new_weights = {k: v / total for k, v in new_weights.items()}
    return new_weights


def propose_new_min_score(threshold_results):
    """Propose min_score as the threshold where precision first exceeds 65%."""
    for tr in threshold_results:
        if tr['precision'] >= 0.65:
            return tr['threshold']
    # Default: keep current if no threshold hits 65%
    return None


def backtest(rows, new_weights, new_min_score):
    """Re-score historical predictions with new weights and threshold."""
    tp_new = 0
    fp_new = 0
    for r in rows:
        new_score = sum(
            (r.get(COMPONENT_COLS[c]) or 0) * new_weights.get(c, 0)
            for c in COMPONENTS
        )
        predicted_burst = new_score >= new_min_score
        actual_positive = r['outcome'] == 'true_positive'
        if predicted_burst and actual_positive:
            tp_new += 1
        elif predicted_burst and not actual_positive:
            fp_new += 1

    total_new = tp_new + fp_new
    precision_new = tp_new / total_new if total_new > 0 else 0.0
    return precision_new, tp_new, fp_new


def load_current_weights(config_path):
    """Parse current weights and min_score from config.yaml."""
    weights = {}
    min_score = 0.65
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            cfg = yaml.safe_load(f)
    except FileNotFoundError:
        return weights, min_score
    except Exception:
        return weights, min_score

    if not cfg:
        return weights, min_score
    eb = cfg.get('early_burst') or {}
    try:
        min_score = float(eb.get('min_score', 0.65))
    except (ValueError, TypeError):
        min_score = 0.65
    metrics = eb.get('metrics', {})
    for comp in COMPONENTS:
        raw = metrics.get(comp, {}).get('weight', 0.25)
        try:
            weights[comp] = float(raw) if raw is not None else 0.25
        except (ValueError, TypeError):
            weights[comp] = 0.25
    return weights, min_score


def apply_config_changes(config_path, new_weights, new_min_score):
    """Update config.yaml with new weights and min_score.

    Loads the config as a YAML dict, modifies values, and writes back.
    This is more robust than string/regex replacement against formatting
    changes, comments, or nested keys.
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = yaml.safe_load(f)

    if not cfg or not isinstance(cfg, dict):
        cfg = {}

    eb = cfg.setdefault('early_burst', {})
    eb['min_score'] = new_min_score
    metrics = eb.setdefault('metrics', {})
    for comp, weight in new_weights.items():
        metrics.setdefault(comp, {})['weight'] = weight

    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(cfg, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def print_proposal(rows, current_weights, current_min_score,
                   comp_corr, threshold_results, new_weights, new_min_score,
                   old_precision, new_precision):
    tp_total = sum(1 for r in rows if r['outcome'] == 'true_positive')
    fp_total = sum(1 for r in rows if r['outcome'] == 'false_positive')

    print("=== Weight Adjustment Proposal ===")
    print(f"Based on {len(rows)} validated predictions (TP: {tp_total}, FP: {fp_total})")
    print()

    print("Current weights:")
    for comp in COMPONENTS:
        print(f"  {comp}: {current_weights.get(comp, 0.25):.4f}")
    print(f"  min_score: {current_min_score}")
    print()

    print("Component Correlation Analysis:")
    for comp in COMPONENTS:
        cc = comp_corr.get(comp, {})
        dp = cc.get('discriminative_power', 0)
        corr_val = cc.get('correlation')
        corr_str = f"corr={corr_val:.3f}" if corr_val is not None else "corr=N/A"
        print(f"  {comp}: TP_avg={cc.get('tp_avg', 0):.3f}, FP_avg={cc.get('fp_avg', 0):.3f}, "
              f"diff={dp:+.3f} ({corr_str})")
    print()

    print("Proposed weights:")
    for comp in COMPONENTS:
        cw = current_weights.get(comp, 0.25)
        nw = new_weights[comp]
        pct = (nw - cw) / cw * 100 if cw > 0 else 0
        marker = " ⚠️ significant" if abs(pct) > 15 else ""
        print(f"  {comp}: {nw:.4f} ({pct:+.1f}%){marker}")
    print(f"  min_score: {new_min_score}")
    print()

    print("Threshold Optimization:")
    print("  Threshold | Precision | Coverage | Count")
    print("  ----------|-----------|----------|-------")
    for tr in threshold_results:
        marker = " <-- current" if tr['threshold'] == current_min_score else ""
        marker += " <-- proposed" if tr['threshold'] == new_min_score and new_min_score != current_min_score else ""
        print(f"  {tr['threshold']:.2f}      | {tr['precision']:.1%}     | {tr['coverage']:.1%}    | {tr['count']}{marker}")
    print()

    print(f"Backtest result:")
    print(f"  Old precision: {old_precision:.1%}")
    print(f"  New precision: {new_precision:.1%} ({new_precision - old_precision:+.1%}pp)")
    print()

    if new_precision >= old_precision:
        print("Recommendation: Changes improve or maintain precision. Safe to apply.")
    else:
        print("WARNING: Backtest shows precision would decrease. Consider rejecting changes.")


def main():
    parser = argparse.ArgumentParser(description="Auto-tune scoring weights from validation outcomes")
    parser.add_argument('--dry-run', action='store_true',
                        help="Show proposal without modifying config")
    parser.add_argument('--apply', action='store_true',
                        help="Apply proposed changes to config.yaml")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        args.dry_run = True

    db = Database()
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    config_path = os.path.join(base_dir, 'config.yaml')

    rows = fetch_outcomes(db)

    if len(rows) < MIN_SAMPLES:
        print(f"Insufficient data for weight adjustment (need >= {MIN_SAMPLES}, got {len(rows)})")
        print("Continue running the pipeline to accumulate more validated predictions.")
        sys.exit(0)

    current_weights, current_min_score = load_current_weights(config_path)

    old_precision, old_tp, old_fp = compute_overall_precision(rows)
    comp_corr = compute_component_correlation(rows)
    threshold_results = compute_threshold_optimization(rows)

    new_weights = propose_new_weights(current_weights, comp_corr)
    proposed_min = propose_new_min_score(threshold_results)
    new_min_score = proposed_min if proposed_min is not None else current_min_score

    new_precision, new_tp, new_fp = backtest(rows, new_weights, new_min_score)

    print_proposal(
        rows, current_weights, current_min_score,
        comp_corr, threshold_results, new_weights, new_min_score,
        old_precision, new_precision
    )

    if args.apply:
        if not os.path.exists(config_path):
            print(f"\nERROR: Config file not found: {config_path}")
            print("Cannot apply changes without an existing config file.")
            sys.exit(1)
        # Backup config
        backup_path = f"{config_path}.bak.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        shutil.copy(config_path, backup_path)
        print(f"\nConfig backed up to: {backup_path}")

        apply_config_changes(config_path, new_weights, new_min_score)
        print(f"Config updated: {config_path}")
    else:
        print("\nRun with --apply to commit these changes.")


if __name__ == '__main__':
    main()
