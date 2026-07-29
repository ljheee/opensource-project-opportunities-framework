# Task 2 Report: L1 采集器（`_fetch_structure_facts` 系列）

(Note: this file previously held a stale report from an earlier plan iteration's "task 2"
(topics cutoff, commit fbfa45a, branch fix/discovery-analysis). Overwritten with the current
Task 2 report for branch feat/tiered-deep-analysis.)

## What I implemented

Added to `DiscoverStage` in `framework/stages/discover.py` (immediately after `_fetch_weekly_contributors`):

- Class constants: `_SRC_EXTS`, `_GEN_PATTERNS`, `_CORE_DIRS`, `_CORE_KEYWORDS`, `_ENTRY_NAMES`
- `_select_core_paths(paths)` — two-layer core-file picker (keyword-under-core-dirs, then entry-file fallback); skips >100KB files and generated-code patterns
- `_parse_tree(tree_entries, partial)` — structural facts (has_tests/has_ci/has_docs/has_examples/partial), collects both `blob` and root-level `tree` entries so partial (root-listing) mode still detects directories; empties `core_paths` when partial
- `_fetch_manifest_deps(full_name, manifest_paths)` — raw.githubusercontent.com fetch (no API quota), parses package.json / pyproject.toml / Cargo.toml / go.mod / requirements.txt, matches against `filters.known_ecosystem_packages`
- `_fetch_issue_health(full_name)` — repo + top-comment issues, PRs filtered via `'pull_request' not in i`, reaction/comment/30d-active aggregates, top-5 issue list
- `_fetch_structure_facts(full_name)` — orchestrator: recursive tree fetch, truncated → root non-recursive fallback with `partial: True`, returns None on total failure; returns facts dict without `fetched_at`

## Deviations from the brief's code (all required to make Step 5 pass)

Step 5 failed as written (`langchain matched: []`). Root-cause investigation found two real bugs in the brief's code, both anticipated by the brief's own Expected note ("若 matched 为空…需检查 dependencies 解析"):

1. **PEP 621 `[project]` parsing was broken two ways:**
   - The brief set `in_deps` only when the section header contains `'dependencies'`, so the `[project]` section (where PEP 621 `dependencies = [...]` lives) was never entered — its own comment claimed PEP 621 support.
   - The extraction regex `"([A-Za-z0-9_.-]+)"` only matches bare quoted names; real-world PEP 621 entries carry version constraints (`"langchain-core>=1.4.7,<2.0.0"`), so even inside a deps array nothing matched.
   - Fix: added an `in_project` flag for `[project]`, and an `_array_names` helper that extracts quoted content then strips version/marker suffixes (`[\s=><~^;\[!(]` split). Name regex requires at least one letter to reject numeric noise (`3.11`) from escaped quotes in environment markers. `[project.optional-dependencies]` and `[dependency-groups]` remain excluded; poetry/cargo `name = version` lines only captured in `*dependencies*` sections (so `[project]`'s `name =`/`version =` are not misread as deps).

2. **Monorepos have no root manifest.** `langchain-ai/langchain`'s root contains only `libs/`; manifests live at `libs/*/pyproject.toml`. The brief's root-only exact-name detection returned None → zero deps.
   - Fix: `_parse_tree` now emits `_manifest_paths` (list): root manifest if present, else up to 10 sorted nested manifests of the highest-priority type present. `_fetch_manifest_deps` takes the list, dispatches parsing per-file by basename, merges deps deduped (order-preserving).
   - Signature change: `_fetch_manifest_deps(self, full_name, manifest_paths: List[str])` (was `manifest_path: Optional[str]`); `_parse_tree` fact key `_manifest_paths` (was `_manifest_path`). Both are internal (`_`-prefixed, popped before output); Task 3 consumes only `_fetch_structure_facts`, which is unchanged.

Everything else follows the brief verbatim (tree-entry collection, truncated degradation, PR filtering, `_github_request`/`GitHubAPIError` usage, priority ordering of manifest types).

## TDD evidence

### RED — Step 1 (before implementation)

```
$ PYTHONPATH=. python3 -c "
from framework.core.config_loader import ConfigLoader
from framework.core.db import Database
from framework.stages.discover import DiscoverStage
s = DiscoverStage(ConfigLoader(), Database())
assert hasattr(s, '_fetch_structure_facts'), 'method missing'
print('OK')
"
AssertionError: method missing   (exit 1)
```

### Intermediate failure driving the fixes

```
requests: {'has_tests': True, 'has_ci': True, 'has_docs': True, 'core_paths': ['src/requests/models.py'], 'partial': False}
AssertionError: []          # langchain matched_ecosystem_packages empty
```

Diagnosis evidence: root listing of langchain-ai/langchain has no manifest (only `libs/` tree entry); `libs/langchain/pyproject.toml` is PEP 621 with `dependencies = ["langchain-core>=1.4.7,<2.0.0", ...]` — the brief's regex extracted 0 names from such lines.

### GREEN — Step 5 (final, verbatim command)

```
requests: {'has_tests': True, 'has_ci': True, 'has_docs': True, 'core_paths': ['src/requests/models.py'], 'partial': False}
langchain matched: ['anthropic', 'langchain-core', 'openai']
hello-world core_paths: [] no_match
L1 fetcher OK
```

### Additional self-checks (synthetic, no network)

- Partial mode with root `tree`-type entries (`tests/`, `docs/`, `examples/` dirs) → has_tests/has_docs/has_examples all True, `core_paths == []`, `core_paths_reason == 'partial'` — confirms the review-mandated tree-entry collection.
- Non-partial: `src/engine/core.py` selected; >100KB file and `_pb2.py`/`.min.js` generated files skipped; `.github/workflows/ci.yml` → has_ci True.
- Offline TOML sanity: PEP 621 multi-line array with version pins and `; python_version < \"3.11\"` marker parsed to `langchain-core, pydantic, async-timeout`; optional-dependencies and build-system requires excluded; poetry section `name = version` lines captured.
- `python3 -m py_compile framework/stages/discover.py` OK.

## Files changed

- `framework/stages/discover.py` (+256 lines) — committed as `2eccd14` "feat: L1 structural facts fetcher (tree, manifest deps, issue health)"

## Self-review findings

- All brief-mandated design points verified: blob+tree collection, truncated→root fallback with partial flag and emptied core_paths, `pull_request` filtering, PEP 621 multi-line arrays, go.mod/requirements noise-line handling.
- `octocat/Hello-World`: no manifest → deps/matched empty (expected); core_paths_reason `no_match` (README-only repo).
- Issue health for requests: `issue_count > 0`, no PR leakage in top_issues.

## Concerns

1. Internal contract differs from brief text (`_manifest_paths` list, `_fetch_manifest_deps` list arg) — reviewers diffing against the brief code will see this; rationale documented above and required by Step 5's acceptance.
2. Monorepo nested-manifest merge fetches up to 10 raw files sequentially (15s timeout each, worst case ~150s on pathological repos). Raw endpoint consumes no API quota; cap keeps it bounded. If latency matters, Task 3's daily budget (`structure_max_per_day`) bounds total exposure.
3. PEP 621 parser only matches double-quoted array elements (TOML single-quoted/literal strings not captured) — rare in practice; acceptable heuristic for L1.
4. Deps from all merged manifests are capped at 200 (`deps[:200]`); monorepos with many sub-packages may truncate tail deps — matched set is computed before truncation, so ecosystem matching is unaffected.
