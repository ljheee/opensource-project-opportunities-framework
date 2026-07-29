# Task 1 Report: config.yaml 新配置键 + ConfigLoader getter

## What was implemented

1. **config.yaml** (`sources.github` 段）:
   - Added `created_within_days: 730`
   - Added `backfill_max_pages: 30`
   - Added `backfill_max_per_day: 50`
2. **config.yaml** (`early_burst.metrics` weights renormalized, thresholds untouched):
   - `star_velocity.weight`: 0.35 → 0.45
   - `activity_index.weight`: 0.25 → 0.35
   - `community_buzz.weight`: 0.25 → 0.0 (buzz out)
   - `novelty_signal.weight`: 0.15 → 0.20
   - New weights sum to 1.00
3. **config.yaml** (`scheduling.incremental`): added `star_change_threshold: 0.05`, `recent_commit_days: 3`, `min_reanalyze_days: 7` alongside existing `max_per_day: 15`.
4. **framework/core/config_loader.py**: inserted two methods verbatim from the brief after `get_star_range`:
   - `get_created_within_days() -> int` (default 730, positive-int coercion)
   - `get_backfill_config() -> Dict` (`max_pages` default 30, `max_per_day` default 50, positive-int coercion via inner `_pos_int`)

## TDD evidence

### RED — Step 1 (before implementation)

```
$ PYTHONPATH=. python3 -c "...assert c.get_created_within_days() == 730..."
Traceback (most recent call last):
  File "<string>", line 4, in <module>
AttributeError: 'ConfigLoader' object has no attribute 'get_created_within_days'
```

Failed exactly as predicted in the brief.

### GREEN — Step 4 (re-run Step 1 after implementation)

```
OK
```

### GREEN — Step 5 (weight renormalization, spec §4 验证项 4)

```
weights OK: 0.705
```

### GREEN — Step 5b (old-vs-new weight flip comparison on real DB, read-only)

```
712 projects, 36 flips
  ('AlexsJones/llmfit', 0.565, 0.659, False)
  ('Alishahryar1/free-claude-code', 0.561, 0.653, False)
  ... (20 rows shown, all old_burst=False)
weight migration OK
```

712 latest-signal rows compared; 36 flips, assertion `36 <= max(2, 712//10=71)` holds. All flips are False→True: with `community_buzz` (which stores a low default ~0.3) zeroed out and its weight redistributed to velocity/activity, projects previously dragged just below 0.65 now cross the threshold. This is the intended effect of the migration; no True→False regressions. The DB was not modified (SELECT only).

## Files changed

- `/Users/lijianhua04/Documents/my-agents/catpawDesk-workspace/github-opportunities/opensource-project-opportunities-framework/config.yaml`
- `/Users/lijianhua04/Documents/my-agents/catpawDesk-workspace/github-opportunities/opensource-project-opportunities-framework/framework/core/config_loader.py`

## Commit

- `a4dbded feat: add discovery/backfill config keys, renormalize scoring weights (buzz out)` (2 files, +31/-4)

## Self-review

- **Completeness:** All three config edits and both getters implemented exactly as the brief specifies, verbatim. New `scheduling.incremental` keys written but not consumed (correct — Task 6/13 territory).
- **Quality:** Getters follow the existing defensive `get_star_range` pattern (defaults on missing/malformed values, positive-int guard). Methods inserted directly after `get_star_range` per the brief.
- **YAGNI:** No extra getters, no consumers wired up, no schema changes.
- **Test evidence:** RED confirmed before edits; Steps 4/5/5b all pass after edits; outputs quoted above.

## Concerns

1. **36 promotion flips (False→True).** The brief anticipated "预期翻转很少" given the DB had 0 early-bursts; 36/712 (5.1%) is within the assertion bound and all promotions, not regressions, but it means the next `discover.py` run will newly flag ~36 projects as early-burst. Downstream stages (schedule/validate) should expect a one-time bump in early-burst candidates.
2. Git warned about auto-configured committer identity (`lijianhua04@MBP-...local`); commit is fine but identity comes from hostname, not explicit git config. Not a code issue.
