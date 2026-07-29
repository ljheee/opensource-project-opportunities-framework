# Task 3 Report: L1 挂载（预算 + 触发 + fail_count + 评分流程接线）

## What I implemented

All changes in `framework/stages/discover.py`, committed as `4e72c1d` on `feat/tiered-deep-analysis`:

1. **Step 1 — counter** (discover.py:63): `self._structures_done = 0` appended after `self._backfills_done = 0` in `__init__`.
2. **Step 2 — `_structure_within_budget(project_id, conn) -> Optional[Dict]`** (discover.py:711): inserted immediately after `_fetch_structure_facts`, verbatim from the brief. Implements:
   - Freshness skip: existing `structure_json` with `fetched_at` < 10 days old returns None.
   - Failure gating: `fail_count >= 3` with `last_fail_at` < 30 days ago returns None (only when `fetched_at` is NULL, i.e. never succeeded).
   - Budget: `self._structures_done >= config.get_structure_max_per_day()` returns None; budget is consumed on attempt regardless of success/failure (intentional per brief).
   - Failure branch MERGES fail info into existing facts (`failure_record = dict(existing)`, preserves old `fetched_at` and all old fact keys) rather than writing a bare failure stub.
   - Success branch stores facts with `fetched_at=now`, `fail_count=0`, returns the facts dict.
3. **Step 3 — scoring-flow wiring** (discover.py:867): `fresh_facts = self._structure_within_budget(project_id, conn)` placed in `_calculate_and_store_burst_score` AFTER the open_issues parsing block (lines 863-866) and BEFORE `calculate_activity_index` (line 868), per the critical placement detail. `fresh_facts` is intentionally unused in this task — reserved for Task 7.

## Verification evidence

### Step 4 (brief script) — two harness bugs found in the script itself

The brief's Step 4 script as written cannot pass regardless of implementation:

- **Bug 1 (operator precedence)**: `lambda pid: calls.append(pid) or {...} if pid != 'a/p2' else None` parses as `(calls.append(pid) or {...}) if pid != 'a/p2' else None` (conditional expression binds looser than `or`), so `calls.append` is never evaluated for `a/p2`. Confirmed empirically: `calls` stays `[]` for p2, so `assert r2b is None and 'a/p2' in calls` (script line 27) always fails.
- **Bug 2 (latent, behind bug 1)**: `_dt.now(_tz)` passes the `timezone` class instead of an instance; raises `TypeError: tzinfo argument must be None or of a tzinfo subclass, not type 'type'`. Needs `_dt.now(_tz.utc)`.

Minimal intent-preserving fixes applied to the harness only (parentheses around the conditional; `_tz` -> `_tz.utc`). Implementation code is byte-identical to the brief.

Command run (temp DB `/tmp/t3_test.db`, monkeypatched fetcher, no network):

```
rm -f /tmp/t3_test.db*; PYTHONPATH=. python3 - <<'EOF' ... (brief script with the two harness fixes) EOF
```

Output:

```
DB migration: added projects.structure_json
budget/freshness/fail-gating OK
```

All four target behaviors verified: budget cap (p2 not attempted when budget=2 exhausted), fail_count write (fail_count=1 in DB after one real failure), freshness skip (p0 skipped on immediate re-call), 3-fail 30-day gating (no fetch attempt after seeded fail_count=3).

### Additional check: failure-merge preservation (not in brief, required by task description)

Seeded a project with 11-day-old successful facts (`has_tests`, `has_ci`, `dependencies`), forced refresh failure, verified old facts and old `fetched_at` survive and only `fail_count`/`last_fail_at` update:

```
failure-merge preserves old facts OK
```

### Compile + placement

```
python3 -m py_compile framework/stages/discover.py  -> OK
grep confirms wiring line at discover.py:867, after open_issues block, before activity calculation
```

## Files changed

- `framework/stages/discover.py` (+75 lines): counter, `_structure_within_budget`, wiring line. Committed as `4e72c1d` with the brief's exact message.

## Self-review findings

- Diff reviewed against the brief: all three code blocks byte-identical to the brief's code.
- `_structure_within_budget` passes `project_id` straight into `_fetch_structure_facts(full_name)` — correct in this codebase since project id IS the full name (verified against `_fetch_weekly_contributors(project_id)` usage at discover.py:872).
- `fresh_facts` is assigned but unused — would trip linters, but intentional (Task 7 consumes it). No linter configured in this repo.
- Budget semantics: attempts (success or failure) consume budget, matching the brief's stated intent (rate-limit protection), differing from backfill's success-only counting.

## Concerns

1. The brief's Step 4 verification script contains two bugs (precedence; `timezone` class vs instance) — no implementation change was needed, but the plan document should be corrected so the reviewer/re-fixer doesn't trip over it. The corrected script is described above.
2. None affecting the implementation itself.
