# Task 2 Report: `_github_request` 可选 headers + topics 查询转向新项目

## Status: DONE_WITH_CONCERNS

## What I Implemented

Three edits in `framework/stages/discover.py`, exactly per the brief:

1. **Step 1 — `_github_request` signature** (now discover.py:63-70): added `headers: Optional[Dict] = None`
   parameter with docstring; before `requests.get(...)`, builds
   `req_headers = {**HEADERS, **headers} if headers else HEADERS` and passes it instead of `HEADERS`.
   Backward compatible: all existing call sites omit `headers` and get identical behavior.
2. **Step 2 — `__init__`**: appended `self.created_within_days = config.get_created_within_days()`
   (Task 1's ConfigLoader method; returns 730 from config.yaml).
3. **Step 3 — `discover_topics` query** (discover.py:462-468): computes
   `cutoff = (datetime.now(timezone.utc) - timedelta(days=self.created_within_days)).strftime('%Y-%m-%d')`,
   appends ` created:>{cutoff}` to the query, and changes sort from `"stars"` to `"updated"`.

## Verification Evidence

### Cutoff assertion (brief Step 4, part 2)

```
$ PYTHONPATH=. python3 -c "
from framework.core.config_loader import ConfigLoader
from framework.core.db import Database
from framework.stages.discover import DiscoverStage
from datetime import datetime, timezone, timedelta
s = DiscoverStage(ConfigLoader(), Database())
cutoff = (datetime.now(timezone.utc) - timedelta(days=s.created_within_days)).strftime('%Y-%m-%d')
print('cutoff =', cutoff)
assert s.created_within_days == 730
"
cutoff = 2024-07-28
```
Assertion passed.

### Dry-run (brief Step 4, part 1) — with one deviation, see Concerns

Head output (`... discover.py --dry-run 2>&1 | head -30`):

```
=== Stage 1: Discover ===
Star range: 50 - 50000
Dry run: True

Source 1: GitHub Topics...
Discovering from 6 topics x 4 languages...
  Skip (skip_pattern:awesome): Tavish9/awesome-daily-AI-arxiv
  Skip (skip_pattern:awesome): leofan90/Awesome-World-Models
  Skip (skip_pattern:examples): PaulDuvall/ai-development-patterns
  ...
```

Full dry-run (no `head`, to prove the whole run completes without Python exceptions):

```
exit=0
Source 1: GitHub Topics...   Found: 507 projects
Source 2: Ecosystem Organizations...   Found: 218 projects
Source 3: GitHub Trending...   Found: 122 projects
Total unique projects: 747
Dry run - not writing to database
  potpie-ai/potpie (github_topic)
  MakazhanAlpamys/Soup (github_topic)
  ... (10 listed)
grep -c "Error\|Traceback" -> 0
```

### Cutoff effectiveness spot-check (extra)

Direct search API call with `created:>2024-07-28` returned only repos created after the cutoff
(oldest in sample: nottelabs/notte, created 2024-12-08).

## Files Changed

- `framework/stages/discover.py` — 12 insertions, 5 deletions (only file in commit)

## Commit

- `fbfa45a` — `feat: topics search targets recent repos (created cutoff + sort=updated)` (on branch `fix/discovery-analysis`)

## Self-Review Findings

- Diff matches the brief's three code blocks verbatim.
- Header merge direction is correct: caller-supplied `headers` override defaults (needed for the
  stargazers `Accept: application/vnd.github.star+json` use case in Tasks 3/5).
- No other `_github_request` call sites require changes; default `headers=None` preserves behavior.
- `datetime`/`timezone`/`timedelta` were already imported at module level; no new imports needed.
- Dry-run did not touch `data/framework.db`.

## Concerns

1. **`.env` token quoting breaks the brief's verbatim extraction command.** `.env` stores
   `GITHUB_TOKEN="ghp_..."` (double-quoted). The brief's extraction
   `GITHUB_TOKEN=$(grep GITHUB_TOKEN .env | cut -d= -f2)` therefore yields a token *with literal
   quotes*, and GitHub returns **401 Bad credentials** (verified via curl: quoted → 401, stripped → 200).
   With the quoted token the dry-run does not crash, but every API call 401s and the retry loop sleeps
   60s/120s per attempt — the run would take over an hour and find 0 projects. The repo's own entry
   scripts avoid this by using `set -a; source .env; set +a`, which strips quotes.
   **Deviation taken:** I killed the 401-looping run and re-ran with
   `GITHUB_TOKEN=$(grep GITHUB_TOKEN .env | cut -d= -f2 | tr -d '"')`. Recommend updating the briefs of
   later tasks (3/5) that use the same extraction, or unquoting the value in `.env`.
2. `sort=updated` with a 730-day window surfaces many recently-created-but-stale repos; the existing
   `_should_skip_repo` stale filter (180 days) already drops them, as seen in the skip output — no action needed.
