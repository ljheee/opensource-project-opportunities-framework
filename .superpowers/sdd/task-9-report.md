# Task 9 Report: analyze.py README 抓取与清洗

## What I implemented

Modified `framework/stages/analyze.py` exactly as specified in the brief:

1. **Imports**: added `import requests` after `import subprocess` (line 14).
2. **Module-level constants** (after `VALID_TIME_HORIZONS`): `_GITHUB_TOKEN`, `_README_HEADERS` (with conditional `Authorization: Bearer` header), `_README_MAX_CHARS = 10000`, and the three compiled regexes `_DATA_URI_RE`, `_IMG_TAG_RE`, `_BADGE_RE`.
3. **`_sanitize_readme(text)`**: strips base64 data-URI images, `<img>/<picture>/<source>` tags, and badge links, then truncates to 10000 chars.
4. **`_fetch_readme(project_id)`**: GETs `https://api.github.com/repos/{project_id}/readme` with 30s timeout, base64-decodes the `content` field, decodes UTF-8 with `errors='replace'`, sanitizes; returns `''` on non-200 or any exception (with a printed warning).
5. **`get_project_data` wiring**: added `proj_dict['readme'] = _fetch_readme(project_id)` immediately after the `proj_dict['peers'] = ...` block.

## TDD evidence

### RED (Step 1, before implementation)

```
$ PYTHONPATH=. python3 -c "
from framework.stages.analyze import _fetch_readme
..."
Traceback (most recent call last):
  File "<string>", line 2, in <module>
ImportError: cannot import name '_fetch_readme' from 'framework.stages.analyze' (/Users/lijianhua04/Documents/my-agents/catpawDesk-workspace/github-opportunities/opensource-project-opportunities-framework/framework/stages/analyze.py)
```

Expected failure confirmed.

### GREEN (Step 3, after implementation)

Step 1 rerun:

```
$ PYTHONPATH=. python3 -c "from framework.stages.analyze import _fetch_readme; ..."
readme OK, 13 chars
```

(octocat/Hello-World README is genuinely ~13 chars: "Hello World!")

Sanitize + fetch verification (with GITHUB_TOKEN from .env):

```
$ PYTHONPATH=. GITHUB_TOKEN=$(grep GITHUB_TOKEN .env | cut -d= -f2 | tr -d '"') python3 -c "..."
sanitize + fetch OK, 10000 chars
```

huggingface/transformers README fetched and truncated to exactly 10000 chars; dirty-input assertions on data URIs / shields.io badges / real content all passed.

## Files changed

- `framework/stages/analyze.py` — 39 insertions, 0 deletions (commit c83cac0).

## Self-review findings

- Diff matches the brief verbatim: import placement, constants, both functions, and the `get_project_data` wiring line.
- Only `framework/stages/analyze.py` was staged and committed; other pre-existing working-tree modifications were left untouched.
- Code compiles and both verification commands pass end-to-end against the live GitHub API.

## Concerns

1. `_fetch_readme` is now called unconditionally inside `get_project_data`, including the non-LLM (heuristic) analysis path — one GitHub API request per analyzed project. This is per the brief; rate-limit impact is mitigated by token auth (5000 req/h) and typical batch sizes, but worth noting for Task 10 integration.
2. `import base64` sits inside `_fetch_readme` rather than the top-level imports — verbatim from the brief, kept as-is.
