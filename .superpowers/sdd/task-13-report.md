# Task 13 Report: 工程杂项（run 脚本分治 + filter --limit + 循环 + .gitignore）

## What I implemented

1. **`.gitignore`**: removed `data/*.db`, `!data/.gitkeep`, `data/reports/*.md`, `!data/reports/.gitkeep` (and their comment). Deviation from the brief, required to meet the brief's own Expected outcome: the remaining `reports/` rule (no leading slash) also matched `data/reports/**`, so the brief's verification (`git check-ignore data/reports/2099-01-01.md` -> exit=1) failed. Changed `reports/` to `/reports/` (root-anchored). Top-level `reports/` (which exists on disk with `2026-04-26.md`) remains ignored; `data/reports/` is now committable.
2. **`framework/stages/filter.py`**: `run_filter(db, dry_run=False, limit=50)`; body passes `limit=limit` to `get_discovered_projects`. `main()` gains `--limit` (int, default 50) with `<= 0` validation printing `ERROR: limit must be a positive integer` and `sys.exit(1)` (`sys` already imported).
3. **`run.sh` / `run_bulk.sh`**: replaced the "discard all local changes" section with the brief's split-handling block verbatim (code/config changes -> ERROR + exit 1; data/-only -> WARN + `git checkout HEAD -- data/` which also clears staged state). Removed the old `git reset HEAD` + `git checkout -- .` lines. Kept the existing `echo "[0/6] git pull..."` / `echo "Git pull..."` lines ahead of the block.
4. **Filter loops**: both scripts now run `filter.py --limit 100` in a `while` loop gated on `discovered`-count > 0, capped at 2 rounds (`_FILTER_ROUNDS`), exactly per the brief (including the `|| echo 0` guard for `set -euo pipefail`).

## Verification evidence

### Step 1: gitignore

```
$ git check-ignore data/framework.db data/reports/2099-01-01.md; echo "exit=$?"
exit=1
$ git check-ignore reports/foo.md; echo "exit=$?"
reports/foo.md
exit=0   # top-level reports/ still ignored
```

(First attempt before anchoring: `.gitignore:18:reports/ data/reports/2099-01-01.md` exit=0 -> fixed via `/reports/`.)

### Syntax

```
$ bash -n run.sh && bash -n run_bulk.sh && echo "syntax OK"
syntax OK
```

### filter.py --limit

```
$ python3 framework/stages/filter.py --limit 0; echo "exit=$?"
ERROR: limit must be a positive integer
exit=1
$ python3 framework/stages/filter.py --limit 5 --dry-run | head -5
=== Stage 3: Semantic Filtering ===
Found 5 projects to classify
... (5 rows shown, limit respected)
```

### Scenario 1: code change -> abort at [0/6], exit 1

```
$ echo "# tmp" >> framework/__init__.py && ./run.sh > /tmp/scen1.log 2>&1; echo "exit=$?"
exit=1
=== AI Project Opportunities Framework - 2026-07-28 ===
WARN: flock command not available (macOS), skipping process lock...
[0/6] git pull...
ERROR: Uncommitted code/config changes detected. Commit or stash them first:
  .gitignore
  framework/__init__.py
  framework/stages/filter.py
  run.sh
```

Abort happened BEFORE any `git pull --rebase` output (log has no pull lines). `framework/__init__.py` restored afterwards (`git checkout --`, verified clean). The other listed files were this task's own uncommitted changes at that point — correct behavior.

### Scenario 2: staged data/-only change -> WARN + continue, staged cleaned

Adaptation: macOS has neither `timeout` nor `gtimeout`. Ran `./run.sh` in background, polled the log (1s interval, 30s cap) until the WARN line appeared AND the staged probe was gone, then killed the process (evidence appeared at 2s — killed long before any push stage, so no push risk).

```
$ echo "probe" >> data/reports/2026-04-22.md && git add data/reports/2026-04-22.md
$ ./run.sh &   # killed after evidence
=== AI Project Opportunities Framework - 2026-07-28 ===
WARN: flock command not available (macOS)...
[0/6] git pull...
WARN: Uncommitted data/ changes detected (likely from a previous failed push). Discarding:
  data/reports/2026-04-22.md
---staged check---
staged cleanup OK
```

Script did NOT exit 1 — log tail shows it proceeded to `git pull --rebase` (which WARNed about no upstream branch) and beyond before being killed. No stray `framework/stages` processes remained (`pgrep -fl` empty). `data/reports/2026-04-22.md` fully restored (no staged or unstaged diff; verified via `git status` and `git diff HEAD`).

## Files changed

- `.gitignore` (-4 ignore lines, `reports/` -> `/reports/`)
- `framework/stages/filter.py` (--limit, run_filter limit param)
- `run.sh` (split change handling + filter loop)
- `run_bulk.sh` (same)

Commit: `b66b402` "fix: abort on code changes in run scripts, loop filter with --limit, unignore data artifacts" (4 files, +52/-30), exactly the files/message from Step 6.

## Notes / deviations from brief expectations

- **Brief said `data/framework.db` had uncommitted (tracked) changes from Task 11 that scenario 2 would discard.** Actually it is UNTRACKED (never committed; `git ls-files --error-unmatch` fails on it). `checkout HEAD -- data/` does not touch untracked files, so nothing was discarded. Both `data/framework.db` and `data/reports/2026-07-28.md` remain untracked and are intentionally NOT part of my commit (Step 6 adds only the 4 source files) — the run scripts will commit them on the next pipeline run, which is now possible precisely because of the .gitignore fix.
- Scenario 2 ordering: ran it AFTER the Step 6 commit instead of before, because with the task's own code changes uncommitted, scenario 2 would (correctly) abort at the code-change check rather than exercise the data/-only path. Script semantics under test are identical.

## Self-review findings / concerns

- `/reports/` anchor deviation was necessary and verified; documented above.
- `run.sh` scenario 1 output listing multiple files confirms the grep split works on multi-file diffs.
- Remaining pre-existing untracked pipeline artifacts (`data/framework.db`, `data/reports/2026-07-28.md`) will be picked up by the next `./run.sh` — first commit of a ~MBs SQLite db to git; that is the intended design per CLAUDE.md, just noting repo-size growth.
- No other concerns.

## Final review fix report

Branch `fix/discovery-analysis`, commits `20eb97f` (code) and `93bf278` (docs).

### Finding 1 (Important): FN baseline predates prediction
- `framework/stages/validate.py` `record_new_predictions` FN loop: baseline query changed from earliest sample (`ORDER BY sampled_at ASC LIMIT 1`) to latest sample on/before the prediction date (`WHERE project_id = ? AND sampled_at <= date(?) ORDER BY sampled_at DESC LIMIT 1`), so backfilled synthetic rows older than `first_seen_at` no longer deflate the baseline and inflate the FN rate.
- Spec `docs/superpowers/specs/2026-07-28-discovery-analysis-fixes-design.md` §2.4 item 2 amended to "取 first_seen_at 当日或之前最近的 star_history 样本" with rationale.
- Plan `docs/superpowers/plans/2026-07-28-discovery-analysis-fixes.md` Task 7 Step 2 code block updated to the same query.

### Finding 2 (Minor): _fn_threshold called per-row + live threshold
- `check_pending_outcomes` FN branch now compares `actual_growth >= predicted_growth` (the row's stored `growth_rate_predicted`, frozen at insert time) instead of calling `_fn_threshold()` per row against live config. Helper retained for insert-time use only.

### Finding 3 (Minor): recall denominator mixed all-source TP with trending-only FN
- `validate.py print_metrics` and `framework/stages/report.py` now compute `tp_trending` via JOIN on `projects.source = 'trending'` and use it in the recall line; labels unchanged ("Recall (trending-source)").

### Finding 4 (Important #2, docs only): incremental trigger discovery-blindness
- CLAUDE.md Six-Stage Pipeline item 4 (schedule.py) now notes: incremental change triggers only see projects still surfaced by discovery; projects dropping out of all discovery sources stop accumulating fresh stars/`last_commit_at` and will not be re-analyzed (known limitation, follow-up).

### Verification (all run, all pass)
1. Task 7 FN regression (`/tmp/fn_test.db`, single sample at first_seen):
   `FN regression OK` — outcome `false_negative`, `stars_at_prediction == 100`.
2. Baseline fix (`/tmp/fn_test2.db`, synthetic -40d row at 100 + -10d row at 140):
   `baseline fix OK: 140 not 100` — pre-first_seen synthetic sample ignored.
3. Frozen threshold (monkeypatched `ConfigLoader` returning `min_score = 99.0`):
   `frozen threshold OK` — stored `growth_rate_predicted = 2.6` still governed the check, outcome `false_negative`.
4. Smoke:
   - `python3 framework/stages/validate.py --metrics-only` — prints metrics cleanly (0 evaluated, no errors).
   - `python3 framework/stages/report.py --date $(date -u +%Y-%m-%d)` — `Report generated: data/reports/2026-07-28.md`.

### Concerns
- None. Smoke DB currently has no evaluated outcomes, so the trending-scoped recall line was exercised only via unit-level SQL shape, not real data output.
