# Task 4 Report: L2 输入组装（analyze.py 核心文件节选 + 骨架事实）

Note: this file previously contained a report from an earlier, archived SDD run
("回溯挂载 + 每日预算", discover.py backfill, commits 52a1d9f/3a80f0c, archived in 56389e4).
It has been replaced per the current task-4 brief's instruction to write here.

## What I implemented

1. Added `_CORE_EXCERPT_MAX = 5000` and module-level `_fetch_core_excerpts(project_id, core_paths) -> List[Dict]` in `framework/stages/analyze.py`, placed immediately after `_fetch_readme` (as briefed). The function fetches up to 3 core file excerpts via `https://raw.githubusercontent.com/{project_id}/HEAD/{path}` with a `Mozilla/5.0` User-Agent and 15s timeout; skips non-string/empty paths, non-200 responses, binary files (NUL byte in first 8192 chars), and `requests` exceptions; truncates content to 5000 chars.
2. Wired `get_project_data`: after `proj_dict['readme'] = _fetch_readme(project_id)`, it parses `proj_dict['structure_json']` into `proj_dict['structure']` (dict or `None` on JSON decode/type errors), and populates `proj_dict['core_excerpts']` via `_fetch_core_excerpts(project_id, (structure or {}).get('core_paths') or [])`.

## TDD evidence

### RED (Step 1, before implementation)

```
Traceback (most recent call last):
  File "<string>", line 2, in <module>
ImportError: cannot import name '_fetch_core_excerpts' from 'framework.stages.analyze' (/Users/lijianhua04/Documents/my-agents/catpawDesk-workspace/github-opportunities/opensource-project-opportunities-framework/framework/stages/analyze.py)
```
(exit code 1 — expected failure)

### GREEN (Step 3, after implementation)

```
OK
edge cases OK
```

Both verifications passed: `psf/requests` excerpt fetch (path/content-length/content assertions) and edge cases (`[]` paths, `None` paths, nonexistent repo -> `[]`).

Additional sanity checks:
- `from typing import List, Dict, Optional, Tuple` already present (analyze.py:16).
- `ast.parse` on the modified file: syntax OK.

## Files changed

- `framework/stages/analyze.py` (+37 lines): new `_CORE_EXCERPT_MAX`, `_fetch_core_excerpts`, and `get_project_data` structure/excerpt wiring.

## Commits

- `ef7d9cb` feat: assemble L2 analysis inputs (structure facts + core file excerpts)

## Self-review findings

- Implementation matches the brief's code verbatim (constant, function, and wiring block).
- `json` and `requests` were already imported; typing imports cover `List`/`Dict`.
- Placement is exactly after `_fetch_readme` and before `_is_whole_word`.
- `get_project_data` wiring uses `proj_dict.get('structure_json')`, safe even if the key were absent from the row dict.

## Concerns

- None blocking. Minor note: git emitted a warning about auto-configured committer identity (`lijianhua04@MBP-D5W0JY5761-2100.local`); commit succeeded as-is. Not a code issue.
