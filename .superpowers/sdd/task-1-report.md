# Task 1 Report: 配置与 schema 基础

## What I implemented

1. **config.yaml**
   - `sources.github.structure_max_per_day: 50` appended after `backfill_max_per_day`.
   - `filters.known_ecosystem_packages` (9 high-level orchestration frameworks/SDKs) appended after `tech_layer_rules`.
   - `early_burst.metrics` replaced verbatim per brief: weights 0.40 / 0.30 / 0.10 / 0.20; `community_buzz.thresholds` keeps `default_score: 0.3` and adds `reaction_total_full: 50`, `active_issues_full: 5`, `avg_comments_full: 5`.

2. **framework/core/config_loader.py**
   - `get_structure_max_per_day() -> int` (default 50, guards non-int / non-positive) inserted immediately after `get_backfill_config`.

3. **framework/core/db.py** — all four edit sites:
   - (a) `_migrate_projects`: appended `structure_json TEXT` via `_add_column_if_missing`.
   - (b) `_migrate_analyses` ALTER section: appended `evidence_json TEXT` after `analyzer_version`.
   - (c) `_migrate_analyses` CHECK-rebuild branch: `analyses_new` CREATE column list, INSERT column list, and SELECT column list all extended with `evidence_json` (SELECT reads it from the old table, safe because the ALTER in (b) runs first in the same call).
   - (d) `_create_analyses` CREATE TABLE: `evidence_json TEXT` after `analyzer_version TEXT`.

## TDD evidence

### RED (Step 1, before changes)

```
Traceback (most recent call last):
  File "<string>", line 5, in <module>
AttributeError: 'ConfigLoader' object has no attribute 'get_structure_max_per_day'
exit=1
```

Exactly the failure mode predicted by the brief.

### GREEN (Step 5, after changes)

Step 1 rerun on a fresh `/tmp/t1_test.db`:

```
DB migration: added projects.structure_json
OK
exit=0
```

Production DB migration (`python3 framework/stages/init_db.py`):

```
DB migration: added projects.structure_json
DB migration: added analyses.evidence_json
Database initialized successfully.
23|structure_json|TEXT|0||0
13|evidence_json|TEXT|0||0
prod migration OK
```

Data integrity sanity check: `projects=1181 rows, analyses=27 rows` — unchanged by the additive migration.

Config load check:

```
{'star_velocity': 0.4, 'activity_index': 0.3, 'community_buzz': 0.1, 'novelty_signal': 0.2}
buzz thresholds: {'default_score': 0.3, 'reaction_total_full': 50, 'active_issues_full': 5, 'avg_comments_full': 5}
pkgs: 9
```

Weights sum to 1.0.

## Files changed

- `config.yaml`
- `framework/core/config_loader.py`
- `framework/core/db.py`

Commit: `2e33ffe feat: config keys and soft-migrated columns for tiered deep analysis` (exact message per brief Step 6).

## Self-review findings

- Verified the brief's verbatim metrics YAML drops the old `thresholds` blocks for `star_velocity`, `activity_index`, and `novelty_signal`. Checked `framework/core/scoring_engine.py`: every threshold read uses `.get(key, <default>)` with defaults identical to the removed YAML values (0.15, 10, 3, 0.3, 6, 2), so scoring behavior is unchanged.
- Idempotency: fresh DBs get both columns via the create/migrate path (verified on `/tmp/t1_test.db`); existing DBs via ALTER (verified on production). The CHECK-rebuild SELECT references `evidence_json` only after the ALTER section has guaranteed the column exists.
- Crash-recovery branch in `_migrate_analyses` (analyses_new rename) returns before the ALTER section; on the next `init_tables()` run the ALTER section runs and adds `evidence_json`, so no gap. Same pre-existing pattern as `analyzer_version`.
- YAGNI: no extra getters, no consumers wired, no schema changes beyond the two columns. requirements.txt untouched.

## Concerns

- `data/framework.db` was modified in the working tree by the Step 5 production migration but intentionally NOT committed, per the brief's Step 6 `git add` scope. The migration is idempotent and the run scripts commit `data/` on the next pipeline run, so this is safe.
- Git warned about auto-configured committer identity (hostname-derived); commit content unaffected.
