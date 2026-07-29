# Task 12 Report: scheduler incremental 冷静期 + 变化双约束

## What I implemented

Rewrote `Scheduler.generate_incremental_tasks` in `framework/core/scheduler.py` per the brief:

- Reads `star_change_threshold` (default 0.05), `recent_commit_days` (default 3), `min_reanalyze_days` (default 7) from `self.config['incremental']`, with `try/except (ValueError, TypeError)` defensive fallbacks.
- Candidate SQL now adds a third gate after the two existing NOT EXISTS clauses:
  - Never-analyzed projects (NOT EXISTS done task) are always eligible.
  - Otherwise requires cooldown elapsed: `COALESCE(datetime(MAX(analyses.analyzed_at)), '1970-01-01') <= datetime('now', '-' || ? || ' days')`.
  - AND a change signal: 7-day star growth >= threshold (scalar subquery; NULL when no 7-day-old sample → not satisfied, intended fallback) OR `datetime(p.last_commit_at) >= datetime('now', '-N days')`.
- INSERT loop unchanged. `schedule.py` already passes the full scheduling dict (confirmed: line 21 `Scheduler(db.db_path, config.get_scheduling_config())`), no change needed there.

## TDD evidence

### RED (Step 1, before the change)

```
AssertionError: cooldown violated: 1 tasks
```

Current code unconditionally generated a task for a project analyzed 1 day ago — cooldown violated, as expected.

### GREEN (Step 1 re-run + Step 4)

Step 1 re-run after the change:

```
cooldown OK
```

Step 4 three-case run: `assert n == 2` passed. The brief's final `ids` assertion printed `{'a/growth', 'a/commit', 'a/quiet'}` — see concerns below. Verified the actually generated tasks with a filtered query:

```
{'project_id': 'a/commit', 'task_date': '2099-01-01', 'status': 'pending'}
{'project_id': 'a/growth', 'task_date': '2099-01-01', 'status': 'pending'}
{'project_id': 'a/quiet',  /* only the fixture 'done' row, no new task */}
trigger rules OK (pending only): {'a/growth', 'a/commit'}
```

So: growth (50% 7-day gain) → eligible; recent commit (yesterday, no growth) → eligible; quiet (no growth, 10-day-old commit) → suppressed. Exactly per spec.

Additional edge sanity (my own, beyond the brief):

- Never-analyzed `scheduled` project with 30-day-old commit → eligible (NOT EXISTS done task branch).
- Project with a done task but no analyses rows, no growth, old commit → suppressed (COALESCE '1970-01-01' prevents starvation but change trigger still gates).
- Empty config `{}` (as analyze.py passes) → defensive defaults engaged, no crash.

```
generated: 1 {'a/new'}
edge cases OK
```

## Files changed

- `framework/core/scheduler.py` (only file committed; +43/-1)

## Self-review findings

- `datetime()` wrapping applied to both `MAX(a.analyzed_at)` and `p.last_commit_at`, matching the production ISO `T...+00:00` format used by fixtures — string comparison would be directionally wrong without it.
- Parameter order in the SQL placeholders matches the tuple `(date, cooldown_days, star_threshold, recent_commit_days, max_tasks)`.
- The change-trigger `AND (...)` grouping is inside the cooldown branch only; the never-analyzed OR-branch is unaffected.
- No other callers of `generate_incremental_tasks` with a mismatched config shape: `schedule.py` passes the full scheduling dict; `analyze.py` passes `{}` but never calls this method (defaults make it safe anyway).

## Concerns

1. **Brief Step 4 assertion defect**: the final check `SELECT project_id FROM tasks` reads the whole tasks table, which includes the three fixture-inserted `done` rows (task_date `2026-01-01`), so the set can never equal `{'a/growth', 'a/commit'}` — it always contains all three fixture projects. The core behavioral assertion (`n == 2`) passed, and filtering to `status='pending' AND task_date='2099-01-01'` yields exactly the expected `{'a/growth', 'a/commit'}`. Behavior is correct; the brief's literal expected output line is unreachable. Suggest the plan author amend Step 4's query to filter pending/new-date rows.
2. Non-blocking: `zsh` glob in `rm -f /tmp/sched_test.db*` fails with `no matches found`; used explicit filenames instead. Environment note only.
