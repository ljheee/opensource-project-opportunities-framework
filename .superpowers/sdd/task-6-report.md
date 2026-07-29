# Task 6 Report: reweight.py 移除 buzz 组件并修复 backtest

## What was implemented

Exactly as the brief specified:

1. `framework/stages/reweight.py:20-25` — `COMPONENTS` reduced to `['star_velocity', 'activity_index', 'novelty_signal']`; `community_buzz` entry removed from `COMPONENT_COLS`.
2. `framework/stages/reweight.py` `backtest()` — rewritten to compute `new_score` dynamically via `sum((r.get(COMPONENT_COLS[c]) or 0) * new_weights.get(c, 0) for c in COMPONENTS)` instead of four hardcoded weight lookups.

## TDD evidence

### RED (Step 1, before change)

```
AssertionError: buzz still in COMPONENTS
```
(exit code 1 — matches expected failure; backtest would also KeyError on `new_weights['community_buzz']`)

### GREEN (Step 4, after change)

Step 1 verification rerun:
```
backtest OK: 1.0 1 0
```

Dry-run smoke test (`python3 framework/stages/reweight.py --dry-run`):
```
Insufficient data for weight adjustment (need >= 20, got 0)
Continue running the pipeline to accumulate more validated predictions.
```
(exit code 0 — matches expected output; 0 outcome rows, normal path, no crash)

## Files changed

- `framework/stages/reweight.py` (commit 2b980b4, +4/-7)

## Self-review findings

- `fetch_outcomes()` still SELECTs and coerces `community_buzz_at_pred` from `prediction_outcomes`. Intentionally left as-is: the brief scopes the change to COMPONENTS/COMPONENT_COLS and backtest; the DB column still exists, and keeping the fetch harmless-extra is consistent with "column retained in history" semantics. All downstream consumers of these rows (`compute_component_correlation`, `propose_new_weights`, `print_proposal`, `backtest`) iterate `COMPONENTS`, so buzz is never scored or proposed.
- `load_current_weights` iterates `COMPONENTS` (now 3 components) and reads weights from config.yaml — consistent with Task 1 which zeroed `community_buzz.weight`; buzz is simply ignored rather than read.
- `apply_config_changes` writes only keys in `new_weights` (3 components), so `--apply` will not touch `community_buzz.weight` in config.yaml.
- Verified commit diff contains only the Task 6 change — no stray pre-existing modifications were swept in.

## Concerns

None.
