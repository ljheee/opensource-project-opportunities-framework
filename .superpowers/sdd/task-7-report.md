# Task 7 Report: 评分反哺（buzz 复活 + activity 增强 + reweight 组件表）

> Note: this file previously held a stale report for a different task
> ("validate.py 召回率回溯 FN 算法"); overwritten per team-lead instruction
> to write the current Task 7 report here.

## What I implemented

1. **`framework/core/scoring_engine.py`**
   - Added `calculate_buzz(issue_health: Optional[Dict]) -> float` after `default_buzz_score` (verbatim from brief): None/non-dict -> `default_buzz_score()` fallback; otherwise weighted blend of reaction_total (0.5), active_issues_30d (0.3), avg_comments (0.2) normalized against `community_buzz` thresholds (`reaction_total_full`/`active_issues_full`/`avg_comments_full`, defaults 50/5/5), clamped to [0,1].
   - Extended `calculate_activity_index` signature with `has_tests=None, has_ci=None`; before `return min(score, 1.0)` added the bonus block (+0.1 when both truthy, +0.05 when one truthy, only when at least one is not None).

2. **`framework/stages/discover.py`** (`_calculate_and_store_burst_score`)
   - Inserted the `structure` parsing block immediately after the Task 3 `fresh_facts = self._structure_within_budget(project_id, conn)` line (before the activity call site, per ordering requirement): prefer `fresh_facts`, else parse `proj['structure_json']` with JSONDecodeError/TypeError guard.
   - Activity call site now passes `has_tests=(structure or {}).get('has_tests')`, `has_ci=(structure or {}).get('has_ci')`.
   - Buzz call site replaced `default_buzz_score()` with `issue_health = (structure or {}).get('issue_health'); buzz_score = self.scoring.calculate_buzz(issue_health); buzz_source = 'real' if issue_health else 'fallback'`.
   - Added `'buzz_source': buzz_source,` to the signals_json dict.

3. **`framework/stages/reweight.py:20-26`**
   - Restored `community_buzz` in `COMPONENTS` and added `'community_buzz': 'community_buzz_at_pred'` to `COMPONENT_COLS`. Verified the column exists: `framework/core/db.py:65` migrates it via `_add_column_if_missing` and `:306` includes it in the table DDL; validate.py already writes it; reweight.py:65/76 already selected/read it.

## TDD evidence

### RED (Step 1, before implementation)

```
Traceback (most recent call last):
  File "<string>", line 5, in <module>
AttributeError: 'ScoringEngine' object has no attribute 'calculate_buzz'
```

### GREEN (Step 1 rerun, after implementation)

```
scoring OK 1.0 0.0 0.3
```

(hot=1.0 saturates all three sub-scores; cold=0.0; None -> default_buzz_score()=0.3; activity a1 == min(a0+0.1, 1.0) assertion passed)

### Step 5 smoke

```
$ python3 framework/stages/reweight.py --dry-run && python3 framework/stages/validate.py --metrics-only >/dev/null && echo "smoke OK"
Insufficient data for weight adjustment (need >= 20, got 0)
Continue running the pipeline to accumulate more validated predictions.
smoke OK
```

MIN_SAMPLES early-exit path works, no crash. `ast.parse` syntax check on discover.py passed; edited region visually re-verified (structure block before activity call site, buzz block after novelty, buzz_source in signals_json).

## Files changed

- `framework/core/scoring_engine.py`
- `framework/stages/discover.py`
- `framework/stages/reweight.py`

Commit: `db8a278 feat: revive buzz as real signal, enhance activity with tests/CI facts, restore buzz in reweight` (3 files, +41/-4)

## Self-review findings

- Ordering constraint satisfied: `structure` is defined before the activity call site; buzz block placed after novelty (order irrelevant there, but matches brief).
- `calculate_buzz` `_f` helper: on ValueError/TypeError it returns the raw default (50/5/5, all positive) — no zero-division risk.
- `issue_health.get(...) or 0` treats 0/None identically — fine since all three metrics are non-negative counts/averages from L1.
- Activity bonus only applies when at least one of has_tests/has_ci is not None, so projects without L1 structure data keep the old score exactly (backwards compatible).
- reweight already read `community_buzz_at_pred` in its SQL (lines 65/76) — restoring the component is consistent with existing code; no schema change needed.

## Concerns

- None blocking. Note (per brief V4): `early_burst_signals` mixes old-weight and new-weight regime rows, so cross-time overall_score comparison needs care — not a code issue introduced here.
