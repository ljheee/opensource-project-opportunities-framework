# Task 4 Report: 回溯挂载 + 每日预算 + synthetic_history 标记

## What I implemented

All 5 edits in `framework/stages/discover.py`, exactly as specified in the brief:

1. **Step 1** — `DiscoverStage.__init__`: appended `self._backfills_done = 0` after `self.created_within_days` (discover.py:62).
2. **Step 2** — Added `_backfill_within_budget(project_id, stars, conn) -> int` immediately after `_backfill_star_history` (discover.py:412-420). Reads `max_per_day` from `config.get_backfill_config()`, returns 0 when budget exhausted, increments counter only when rows were actually written.
3. **Step 3** — `run()` store loop (discover.py:790-796): hoisted `new_stars` and call `_backfill_within_budget` **before** `_sample_star_count`, so the "no history" check in `_backfill_star_history` is valid for first-seen projects.
4. **Step 4** — `run()` existing-projects sampling loop (discover.py:822): same guard call before `_sample_star_count`.
5. **Step 5** — `_calculate_and_store_burst_score` `signals_json` now includes `synthetic_history: bool`, true when the earliest star_history sample predates the project's `first_seen_at` date (i.e. the history was reconstructed by backfill). Verified both history paths (`get_project_star_history` and the shared-conn query) return dicts, so `h['sampled_at']` is safe.

## Verification evidence

### Brief Step 6 (live run, budget=2)

Config prep:
```
$ python3 - <<'EOF' ... EOF   # wrote /tmp/config_test.yaml with backfill_max_per_day=2
config written
```

Live drive against real projects:
```
$ PYTHONPATH=. GITHUB_TOKEN=$(grep GITHUB_TOKEN .env | cut -d= -f2 | tr -d '"') python3 -c "..."
budget OK, backfills done: 0
```

Result: the `SELECT ... WHERE NOT EXISTS (star_history)` query returned **zero rows** — every project in the current DB already has star_history, so `_backfill_star_history` short-circuited before any network call. Assertion `s._backfills_done <= 2` passed but is inconclusive (no project was actually backfilled). Per the teammate instructions, I also ran the monkeypatched variant.

### Monkeypatched variant (temp DB copy at /tmp/framework_test.db, no network)

Replaced `_fetch_stargazer_timestamps` with a lambda returning 3 days of timestamps; cleared history for 3 projects on the **temp copy only** (data/framework.db untouched):

```
  Backfilled 3 days of star history for jingyaogong/minimind
jingyaogong/minimind -> 3 rows
  Backfilled 3 days of star history for explosion/spaCy
explosion/spaCy -> 3 rows
Lightning-AI/pytorch-lightning -> 0 rows
budget OK, backfills done: 2
```

Proves: counter increments per successful backfill and caps at the configured budget of 2; the 3rd project returns 0 rows without touching the API.

### synthetic_history flag

For a backfilled existing project (first_seen_at long ago), flag correctly stays false:
```
signals_json: {..., "current_stars": 48288, "synthetic_history": false}
```

For a simulated newly-discovered project (first_seen_at = today, backfilled rows 2026-07-25..27):
```
0x4m4/hexstrike-ai -> 3 rows
signals_json: {..., "current_stars": 8296, "synthetic_history": true}
synthetic flag OK
```

Both temp DB copies were deleted after the runs; `data/framework.db` was never modified.

## Files changed

- `framework/stages/discover.py` — 20 insertions, 2 deletions (commit 52a1d9f)

## Self-review findings

- Diff matches the brief verbatim; syntax check (`ast.parse`) passes.
- Ordering is correct in both loops: backfill precedes sampling, so first-seen projects are eligible for backfill before `_sample_star_count` creates today's row (which would otherwise make the "no history" check permanently false).
- Budget counter only increments on `written > 0`, so 404 fast-fails / already-historied projects don't consume budget — sensible behavior.
- Minor known limitation (by design, not changed): history query is limited to the last 35 days, so `synthetic_history` can be a false negative if all synthetic rows are older than 35 days. Matches the brief's spec; flagging for awareness.

## Concerns

- The live Step 6 verification was inconclusive because the production DB currently has zero projects without star_history. The budget logic is proven only via the monkeypatched variant. On the next real discover run, new first-seen projects will exercise the live path.

## Guard fix report

**Problem**: the original guard skipped backfill when ANY star_history row existed. All 712 legacy projects have exactly 1 sample each (2026-04-26 run), so the intended legacy backfill never triggered.

**Predicate chosen**: skip when `COUNT(*) >= 7 OR COUNT(DISTINCT sampled_at) >= 3`.

**Why**:
- `COUNT(*) >= 7` covers projects with a full 7-day velocity window of real depth (and large backfills).
- `COUNT(DISTINCT sampled_at) >= 3` is the idempotency marker for completed backfills: a backfill writes one row per active stargazer day, and legacy projects always carry their 1 early sample plus today's sample (sampling runs right after backfill in ingest), so any completed backfill reaches >= 3 distinct dates by construction, or by the next daily run at the latest. A plain `COUNT(*) >= 7` alone re-triggered on the second call (4 < 7 after a 3-day backfill).
- An `EXISTS(sampled_at < now-7d)` clause was rejected: the legacy April row is older than 7 days, so it would wrongly mark legacy projects as backfilled.
- A "row within 35-day window" predicate was rejected: today's real sample (written after backfill on day 1) would falsely look like backfill evidence... actually backfill runs before sampling, but the distinct-date predicate is simpler and independent of ingest ordering.

**Three-case verification** (temp DB, monkeypatched `_fetch_stargazer_timestamps`):
- 1-row legacy (2026-04-26): backfilled, `n_legacy == 3`
- 7 daily samples: skipped, `n_deep == 0`
- second call on backfilled legacy: skipped, `n_second == 0` (idempotent; legacy total rows: 4)

**Real-DB read-only confirmation**: 712 projects have `COUNT(*) < 7` in `data/framework.db` — all will now be eligible for backfill under the daily budget.

Commit: 3a80f0c "fix: backfill guard uses history depth so 1-sample legacy projects backfill"
