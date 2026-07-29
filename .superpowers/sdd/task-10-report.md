# Task 10 Report: prompt 模板接入 README + analyzer_version 参数化

## What was implemented

All 4 edits from the brief, verbatim:

1. **Step 1 — Prompt template** (`framework/prompts/ai_analyze.md`): Inserted the
   `## Project README (excerpt)` section (with untrusted-content warning and
   `<readme>{readme_excerpt}</readme>` tags) immediately before the
   `## Peer Comparison (Same Category)` heading, exactly as the brief's markdown snippet.

2. **Step 2 — `_format_prompt` values** (`framework/stages/analyze.py`, in
   `generate_analysis_with_llm`): Appended
   `'readme_excerpt': project.get('readme') or '_README unavailable._',` to the values dict.

3. **Step 3 — `store_analysis_and_opportunities` signature**
   (`framework/stages/analyze.py:299`): Added `analyzer_version: str = 'llm-v1'` parameter;
   the INSERT now passes `analyzer_version` instead of the hardcoded `'v1.0'`.

4. **Step 4 — Call site** (`framework/stages/analyze.py:863-878` in `run_analysis`):
   LLM/heuristic branches set `analyzer_version` to `'llm-v1'` / `'heuristic-v1'` and pass it
   to `store_analysis_and_opportunities`, exactly as the brief's snippet.

Note: actual line numbers drifted slightly from the brief (299/325/610/863 vs 260/288/559/822)
because earlier tasks shifted the file, but all anchor code matched exactly.

## Verification evidence

Step 5 command (run verbatim with `PYTHONPATH=.`):

```bash
PYTHONPATH=. python3 -c "
from framework.stages.analyze import _format_prompt
tpl = open('framework/prompts/ai_analyze.md').read()
out = _format_prompt(tpl, {'readme_excerpt': 'README {not_a_placeholder} 内容', 'name': 'x'})
assert 'README {not_a_placeholder} 内容' in out, 'readme not injected'
assert '{readme_excerpt}' not in out, 'placeholder left'
print('prompt injection OK')
"
```

Output: `prompt injection OK` (braces in README content not double-replaced; placeholder consumed).

Additional checks:

```bash
python3 -m py_compile framework/stages/analyze.py   # -> compile OK
grep -rn "store_analysis_and_opportunities" framework/ --include="*.py"
# -> only definition (analyze.py:299) and the single updated call site (analyze.py:877)
```

## Files changed

- `framework/prompts/ai_analyze.md` (+10 lines)
- `framework/stages/analyze.py` (+11/-3 lines)

## Commit

- `0e99a16` — `feat: inject sanitized README into LLM prompt, tag analyzer_version`
  (on branch `fix/discovery-analysis`; commit command exactly as brief Step 6)

## Self-review findings

- Diff reviewed with `git show`: all four hunks match the brief character-for-character
  (prompt section wording, placeholder name, fallback string `_README unavailable._`,
  default version `'llm-v1'`, heuristic tag `'heuristic-v1'`).
- Backward compatibility: `analyzer_version` has a default, so any out-of-tree callers are safe;
  in-tree there is exactly one caller and it passes the parameter explicitly.
- Consumes `project['readme']` added by Task 9 (`get_project_data`); `project.get('readme')`
  returns None for rows without README, falling back to `_README unavailable._` — correct.

## Concerns

- None functional. One note: existing rows in `analyses` recorded before this change keep the
  old `'v1.0'` version string, so historical rows are not tagged llm/heuristic — expected,
  since prior runs did not record the distinction.
