# Task 3 Report: Stargazers 时间戳回溯核心函数

## What was implemented

Two methods on `DiscoverStage` in `framework/stages/discover.py`, inserted immediately after `_sample_star_count` (verbatim per brief Step 2):

- `_fetch_stargazer_timestamps(full_name, stars) -> List[str]` — pages the stargazers endpoint newest-first (from `min(ceil(stars/100), 400)` down to 1) with `Accept: application/vnd.github.star+json`, bounded by `get_backfill_config()['max_pages']`, stopping when a page's earliest `starred_at` is older than the 35-day cutoff.
- `_backfill_star_history(project_id, stars, conn=None) -> int` — skips if the project already has star_history rows (idempotent), buckets timestamps per UTC day (`ts[:10]`, pure `YYYY-MM-DD`), computes `baseline = max(stars - covered, 0)`, and writes cumulative daily rows via `INSERT OR IGNORE` matching `UNIQUE(project_id, sampled_at)`.

Commit: `0b82309 feat: backfill star history from stargazer timestamps on first-seen projects` (89 insertions, discover.py only).

## TDD evidence

### RED — Step 1 (before implementation)

```
$ PYTHONPATH=. python3 /tmp/verify_backfill.py
AssertionError: method missing
```

### GREEN — Step 3 (after implementation)

```
$ PYTHONPATH=. python3 /tmp/verify_backfill.py
OK
```

### Step 4 — E2E: brief script FAILS for environmental reasons; adapted E2E PASSES

**Repo used:** `egoist/kero` (669 stars, created 2026-07-18, currently bursting: 162 stars in the last 3 days per WatchEvents).

**Brief script as written fails** — the GitHub stargazers endpoint is blocked in this sandbox:

- `GET /repos/{owner}/{repo}/stargazers` returns **404 for every repo tested** (`egoist/kero`, `aipoch/open-science`, `d3/d3`), with or without the star+json Accept header, encoded or plain slash, with a valid token (token verified: `/user` 200, `/repos/...` 200, `/commits`/`forks`/`issues`/`events` 200, rate_limit 5000).
- Unauthenticated request to the same public endpoint returns **401** (GitHub proper returns 200) — signature of an egress gateway.
- GraphQL `stargazers { edges { starredAt } }` returns **empty edges** while `stargazerCount` works — stargazer data is stripped at both API layers.
- `/etc/hosts` contains `127.0.0.1 github.zh-cns.top ##+sec`, confirming local security tooling around GitHub traffic.

Brief-script run output (page fetch retried with 60s/120s backoff, then):

```
Backfill page 7 failed for egoist/kero: Failed after 3 attempts: 404 Client Error: Not Found for url: https://api.github.com/repos/egoist%2Fkero/stargazers?per_page=100&page=7
AssertionError: no rows written
```

**Adapted E2E** (`/tmp/verify_backfill_e2e_events.py`): only `_fetch_stargazer_timestamps` is monkeypatched to source **real** star timestamps from the repo events API (`WatchEvent.created_at`, endpoint reachable, 162 timestamps collected); `_backfill_star_history` runs verbatim against a real repo and `/tmp/backfill_test_events.db`:

```
actual stars: 669
  [events-api] collected 162 WatchEvent timestamps
  Backfilled 3 days of star history for egoist/kero
{'sampled_at': '2026-07-26', 'stars': 532}
{'sampled_at': '2026-07-27', 'stars': 624}
{'sampled_at': '2026-07-28', 'stars': 669}
E2E OK: 3 days, latest = 669 / actual 669
```

Asserts passed: row count == returned count > 0; second call returns 0 (idempotent); strictly non-decreasing; `sampled_at` all pure 10-char dates. Final value equals actual 669 — note this is partly by construction (`baseline = stars - covered` absorbs stars outside the fetched window); the real unstar-overcount deviation (spec §2.2) could not be exercised without the live stargazers endpoint.

## Files changed

- `framework/stages/discover.py` (+89 lines, two methods). Committed as `0b82309`.
- `/tmp/verify_backfill.py`, `/tmp/verify_backfill_e2e.py`, `/tmp/verify_backfill_e2e_events.py` — verification scripts (temp, not committed).

## Self-review findings

1. **Code matches brief verbatim.** Signature, conn/commit/close discipline, `INSERT OR IGNORE`, pure-date format, idempotency guard — all as specified; aggregation logic verified against real timestamp data.
2. **Aggregation correctness:** page iteration newest-first with earliest-per-page cutoff break is sound (stargazers pages are oldest-first within a page, so older pages only get older). Per-day bucketing via `ts[:10]` is UTC-consistent with the ISO timestamps.

## Concerns

1. **`quote(full_name, safe='')` encodes `/` to `%2F`** (discover.py `_fetch_stargazer_timestamps`). GitHub's API routes `{owner}/{repo}` as separate path segments and is known to 404 on encoded slashes. I could not confirm live (endpoint blocked here — both forms 404), but on an unrestricted network `repos/egoist%2Fkero/stargazers` will very likely 404. Recommend changing to `quote(full_name, safe='/')` in a follow-up; flagged for the Task 3 reviewer rather than deviating from the brief.
2. **Brief Step 4 script defect (plan-level):** the verbatim E2E script never inserts a `projects` row, but `star_history.project_id REFERENCES projects(id)` and `Database` sets `PRAGMA foreign_keys=ON` — so even with a working stargazers endpoint, the script fails with `sqlite3.IntegrityError: FOREIGN KEY constraint failed`. My adapted script inserts a minimal project row first; Task 4's real pipeline inserts projects before backfill so production flow is unaffected, but the plan's verification script should be fixed.
3. **`_github_request` retries 404s** with 60s/120s backoff (Task 2 behavior): one unreachable repo costs ~3 minutes before `GitHubAPIError` is raised and the backfill loop breaks. Worth considering not retrying 4xx in a future task.
4. **`max_per_day` from `get_backfill_config()` is unused** by this task's code (only `max_pages` is read). Presumably consumed in Task 4; noted for completeness.
5. Step 4's "final-curve vs actual" comparison is weakened: equality is guaranteed by the baseline construction when only a partial window of timestamps is available. True end-to-end validation of the stargazers path still needs a run in an unblocked network environment (e.g., the GitHub Actions runner).

---

## Fix report (post-review, commit `0d829e5`)

Two confirmed review concerns were fixed in `framework/stages/discover.py`:

### Diff 1 — URL-encoded slash in stargazers path (concern #1)

```diff
-                    f"https://api.github.com/repos/{quote(full_name, safe='')}/stargazers",
+                    f"https://api.github.com/repos/{quote(full_name, safe='/')}/stargazers",
```

`safe=''` encoded `/` as `%2F`, which real GitHub returns 404 for; the slash is now preserved as a path separator.

### Diff 2 — 404 fast-fail in `_github_request` (concern #3)

```diff
+                if response.status_code == 404:
+                    raise GitHubAPIError(f"Not found: {url}", status_code=404)
+
                 response.raise_for_status()
```

Placed after the 429 handling block and before `raise_for_status()`. Deleted/renamed repos now raise immediately instead of burning the 60s/120s retry loop. No other status handling changed.

### Verification commands and outputs

1. Import check:
   ```
   $ PYTHONPATH=. python3 -c "from framework.stages.discover import DiscoverStage; print('import OK')"
   import OK
   ```
2. Backfill verify script:
   ```
   $ PYTHONPATH=. python3 /tmp/verify_backfill.py
   OK
   ```
3. Logic E2E (monkeypatched fetch, no network for backfill; live 404 request with GITHUB_TOKEN):
   ```
   Backfilled 3 days of star history for a/b
   backfill logic OK: [{'sampled_at': '2026-07-26', 'stars': 2}, {'sampled_at': '2026-07-27', 'stars': 3}, {'sampled_at': '2026-07-28', 'stars': 4}]
   404 fast-fail OK (0.8s)
   ```
   Asserts passed: `n == 3`, values strictly non-decreasing with final value 4, second backfill call idempotent (returns 0), and the 404 on a nonexistent repo raised `GitHubAPIError` in 0.8s (< 30s threshold, proving no retry burn).
