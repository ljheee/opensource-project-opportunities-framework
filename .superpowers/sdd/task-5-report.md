# Task 5 Report: Contributors 实采（commits API）

## What I Implemented

Exactly per the brief, in `framework/stages/discover.py`:

1. **New method `_fetch_weekly_contributors(full_name) -> Optional[int]`** (inserted after `_backfill_within_budget`, now at discover.py:428): calls `GET /repos/{full_name}/commits?since=<7d ago>&per_page=100` via `_github_request`, dedupes distinct commit authors by `author.login` (lowercased), falling back to `commit.author.email` when the GitHub user object is absent. Returns `None` on `GitHubAPIError` or non-list response; returns the distinct author count otherwise (0 is a valid result). Uses `quote(full_name, safe='/')` verbatim as specified.

2. **Scoring integration in `_calculate_and_store_burst_score`** (discover.py:540-551): replaced the hardcoded `calculate_novelty(..., 1)` with: read `proj['contributor_count']`; if NULL, fetch via `_fetch_weekly_contributors(project_id)` and on success UPDATE `projects.contributor_count`; pass the count to `calculate_novelty`, falling back to 1 only when both DB value and fetch are unavailable. `project_id` is the repo full name (same convention as `_fetch_stargazer_timestamps(project_id, ...)`), so the parameter passing is consistent.

## Verification Evidence

### Step 3 (brief, verbatim)

```
$ PYTHONPATH=. GITHUB_TOKEN=$(grep GITHUB_TOKEN .env | cut -d= -f2 | tr -d '"') python3 -c "
from framework.core.config_loader import ConfigLoader
from framework.core.db import Database
from framework.stages.discover import DiscoverStage
s = DiscoverStage(ConfigLoader(), Database())
n = s._fetch_weekly_contributors('octocat/Hello-World')
print('octocat/Hello-World weekly contributors:', n)
assert n is not None
"
octocat/Hello-World weekly contributors: 0
```

0 is the valid real result for that repo (no recent commits); assertion passed, exit 0.

### Positive-case check (additional, per team-lead instruction)

```
$ ... s._fetch_weekly_contributors('huggingface/transformers') ...
huggingface/transformers weekly contributors: 42
```

Integer >= 1, assertion passed, exit 0.

### End-to-end smoke test of the scoring integration (in-memory DB, real API)

Inserted a `huggingface/transformers` row with `contributor_count = NULL` into an in-memory DB (`dbmod.DB_PATH = ':memory:'`), ran `_calculate_and_store_burst_score`:

```
contributor_count backfilled: 42
novelty_score: 0.2 overall_score: 0.49250000000000005
re-fetch calls on second run: 0
```

- The real fetch result (42) was backfilled into `projects.contributor_count` and used in novelty scoring.
- Second run with a stubbed `_fetch_weekly_contributors` made **zero** fetch calls — the NULL-only guard works; no repeat API traffic for already-sampled projects.

## Commit

```
1fe0561 feat: sample real weekly contributors for novelty signal
 framework/stages/discover.py | 38 +++++++++++++++++++++++++++++++++++++-
 1 file changed, 37 insertions(+), 1 deletion(-)
```

Only `framework/stages/discover.py` was staged, exactly as Step 4 specifies. Pre-existing unrelated modifications in the working tree (config.yaml, other framework files) were left untouched.

## Files Changed

- `/Users/lijianhua04/Documents/my-agents/catpawDesk-workspace/github-opportunities/opensource-project-opportunities-framework/framework/stages/discover.py` (+37/-1)

## Self-Review Findings

1. **Transaction persistence verified**: in the `should_close` path, the single `conn.commit()` at discover.py:588-589 commits both the `contributor_count` UPDATE and the signals INSERT atomically; in the shared-conn path the caller commits. Neither path loses the backfill.
2. **Idempotency**: NULL-only fetch means one API call per project ever (unless the first fetch fails, in which case it retries on the next scoring run — desired behavior).
3. **Failure mode**: on API failure the method returns None, prints a diagnostic, and scoring falls back to contributor count 1 — identical behavior to the pre-change hardcoded value. No regression risk on network errors.
4. **Redundant `or {}` in `((c.get('author') or {}) or {})`**: kept verbatim from the brief; harmless.

## Concerns

1. **Truncation at 100 commits**: `per_page=100` with no pagination means repos with >100 commits in 7 days (e.g. very active monorepos) get contributor counts sampled from only the newest 100 commits. This is inherent to the brief's design and acceptable for a novelty heuristic, but worth noting.
2. **Stale backfill**: once backfilled, `contributor_count` is never refreshed, so the novelty signal reflects the week of first scoring, not the current week. Again per design (the column doubles as a cache), but a long-lived project's novelty may drift from reality over time.
