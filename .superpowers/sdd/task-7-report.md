# Task 7 Report: validate.py 召回率回溯（FN 算法）

## What I Implemented

All four edits to `framework/stages/validate.py`, exactly per the brief:

1. **Step 1** — Added `from datetime import datetime, timezone`, `from framework.core.config_loader import ConfigLoader`, and the `_fn_threshold()` helper (`min_score * 8 * 0.5`, falls back to 0.65 on any exception). Verified `ConfigLoader().get_early_burst_config().min_score` exists (config_loader.py:23,69).
2. **Step 2** — `record_new_predictions(db, min_days_for_fn: int = 7)`: inserted the FN-candidate block before `conn.commit()`. Subquery SELECT list includes `is_early_burst` (required by the outer filter); outer filter `e.is_early_burst IS NOT 1` matches 0 and NULL. Inserted rows have all four component columns NULL (direction marker) and `growth_rate_predicted = fn_threshold`. `checked_at` = today (UTC) when a star_history baseline exists, else `first_seen_at` date.
3. **Step 3** — Added `po.star_velocity_at_pred` to the `check_pending_outcomes` SELECT, and replaced the flat TP/FP judgment with the direction branch: `is_tp_candidate = row['star_velocity_at_pred'] is not None`. TP branch = original logic verbatim; FN branch labels `false_negative` when `actual_growth >= _fn_threshold()` else `true_negative`. UPDATE statement unchanged.
4. **Step 4** — `print_metrics`: added FN/TN counts after the `pending` count, and the recall print lines after the precision block (self-review correction, see below).

## Verification Evidence

### Step 5 constructed-data test (verbatim from brief, /tmp/fn_test.db)

```
Recorded 1 new FN candidates
Recorded 0 new predictions
Updated 1 pending outcomes
{'id': 1, 'project_id': 'a/b', 'predicted_at': '2026-07-18 13:43:21', 'stars_at_prediction': 100,
 'overall_score_at_prediction': 0.4, 'star_velocity_at_pred': None, 'activity_index_at_pred': None,
 'community_buzz_at_pred': None, 'novelty_at_pred': None, 'growth_rate_predicted': 2.6,
 'checked_at': '2026-07-28', 'stars_now': 500, 'growth_rate_actual': 40.0, 'outcome': 'false_negative'}
FN pipeline OK
```

Growth = (500-100)/10 = 40 stars/day >= 2.6 → `false_negative`. Component columns NULL as designed. Passed on first run (no date-boundary adjustment needed).

### TP-direction regression sanity check (my own, /tmp/fn_tp_test.db)

Early-burst project (score 0.80, components 0.9/0.8/0.7/0.8), 100 stars at record time → 800 at check:
`outcome == 'true_positive'`, `growth_rate_actual == 70.0`, component columns preserved (0.9 etc.). Confirms the direction branch does not reclassify existing TP rows.

### Real-DB smoke test

```
$ python3 framework/stages/validate.py --metrics-only
=== Prediction Validation Metrics ===
Total evaluated: 0  (TP: 0, FP: 0)
Pending (too recent): 0
Recall candidates — FN (missed bursts): 0, TN: 0
--- Score Bucket Calibration ---
```

ConfigLoader loads the real config.yaml without error; FN/TN lines render even with zero evaluated rows.

## Files Changed

- `framework/stages/validate.py` (+95/-8)

## Self-Review Findings

1. **Fixed during self-review**: I initially placed the recall print lines after the "Pending" line instead of after the precision block as the brief specifies. Moved them to after the `if total > 0:` precision block (outer indentation, so they still print when total == 0), re-verified, and amended the commit.
2. **Cosmetic ordering note (per brief, not a defect)**: "Recorded N new FN candidates" prints before "Recorded N new predictions" because the brief places the FN block before `conn.commit()` while the TP count prints after it.
3. FN rows' `growth_rate_predicted` (2.6) is written back unchanged by the UPDATE in the FN branch — consistent with the brief's note that `predicted_growth` is unused in the FN branch but the UPDATE stays as-is.
4. `checked_at` set at record time is overwritten by the UPDATE at check time — same behavior as the existing TP flow.
5. Double-record safety: both TP and FN queries guard with `NOT EXISTS (prediction_outcomes)`; a project whose latest signal flips to `is_early_burst=1` is excluded from FN by the `IS NOT 1` filter.

## Concerns

None blocking. One latent note: FN recall denominator (`tp + fn`) mixes TP candidates from all sources with trending-only FN candidates, so "Recall (trending-source)" is an approximation — this matches the brief's formula exactly.
