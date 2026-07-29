# Task 5 Report: prompt 模板改造与 values 接线

**Status:** DONE
**Commit:** b511911 `feat: prompt contract for evidence-grounded analysis with injection guards`
**Branch:** feat/tiered-deep-analysis

(Note: this file previously contained a stale report from an earlier plan's "Task 5" (contributors sampling); overwritten per current task assignment.)

## What I implemented

### Step 1: prompt 模板改造 (`framework/prompts/ai_analyze.md`)

1. Inserted three new input sections BEFORE `## Project README (excerpt)`:
   - `## Structural Facts (deterministic, from repo tree/manifest/issues)` with `<structural-facts>{structure_facts}</structural-facts>`
   - `## Core Implementation Excerpts` with `<core-implementation>{core_implementation}</core-implementation>` and PRIMARY-evidence-for-innovation guard
   - `## Community Signals (top issues)` with `<community-signals>{community_signals}</community-signals>` and PRIMARY-evidence-for-problem guard
   - All three carry the untrusted-third-party-content injection guard.
2. Appended instruction 6 (**Evidence discipline**) to the end of `## Analysis Instructions`, verbatim from the brief.
3. Added four output schema fields after `"overall_score": 1-10,`: `innovation_evidence`, `problem_evidence`, `confidence`, `cannot_determine`.
4. Appended the four Field Guidelines bullets.

### Step 2: values 接线 (`framework/stages/analyze.py`)

1. Added three formatter functions immediately after `_format_prompt` (analyze.py:548-597), exactly per the brief:
   - `_format_structure_facts` (flags, dependencies capped at 30, matched packages, core_paths + reason, issue_health, partial-tree note)
   - `_format_core_excerpts` (max 3 excerpts, FOUR-backtick fences so embedded triple-backtick content does not break the fence)
   - `_format_community_signals` (issue stats + numbered top issues with reactions/comments; distinct fallback when issues disabled/fetch failed)
2. Wired three values into the `_format_prompt` dict in `generate_analysis_with_llm` right after the `'readme_excerpt'` line:
   - `'structure_facts': _format_structure_facts(project.get('structure'))`
   - `'core_implementation': _format_core_excerpts(project.get('core_excerpts'))`
   - `'community_signals': _format_community_signals(project.get('structure'))`

These consume Task 4's `structure` / `core_excerpts` keys from `get_project_data` (already present in the same file, analyze.py:264-274).

## Verification evidence

Ran the brief's Step 3 command verbatim:

```
$ PYTHONPATH=. python3 -c "
from framework.stages.analyze import _format_prompt, _format_structure_facts, _format_community_signals
tpl = open('framework/prompts/ai_analyze.md').read()
s = _format_structure_facts({...})
c = _format_community_signals({... 'top_issues': [{'title': 'bug {name}', ...}]})
out = _format_prompt(tpl, {'structure_facts': s, 'core_implementation': 'CODE', 'community_signals': c, 'name': 'REALNAME'})
assert 'CODE' in out and 'has_tests: True' in out
assert 'bug REALNAME' not in out and 'bug {name}' in out  # content placeholders NOT replaced
for ph in ('{structure_facts}', '{core_implementation}', '{community_signals}'):
    assert ph not in out, ph
print('prompt wiring OK')
"
prompt wiring OK
```

Output: `prompt wiring OK` — all assertions passed, including the single-pass guarantee (content-side `{name}` inside an issue title is NOT substituted) and that all three new template placeholders are fully replaced. The module import itself also serves as a compile check for the new functions.

## Files changed

- `/Users/lijianhua04/Documents/my-agents/catpawDesk-workspace/github-opportunities/opensource-project-opportunities-framework/framework/prompts/ai_analyze.md` (+33)
- `/Users/lijianhua04/Documents/my-agents/catpawDesk-workspace/github-opportunities/opensource-project-opportunities-framework/framework/stages/analyze.py` (+54)

Commit: `b511911` — exactly the two files staged per Step 4; unrelated working-tree modifications left untouched.

## Self-review findings

- Diff reviewed via `git show b511911`; every hunk matches the brief's markdown/python blocks.
- Minor intentional deviation: the brief's inline comment on the four-backtick fence was in Chinese; I translated it to English (`# Four-backtick fences: file content itself may contain triple backticks (review fix)`) because the entire file is English-only. Semantics unchanged.
- Formatter functions sit after `_format_prompt` and before `generate_analysis_with_llm`; module-level defs, no ordering hazard.

## Concerns

- None blocking. Note for Task 6: the four new schema fields (`innovation_evidence`, `problem_evidence`, `confidence`, `cannot_determine`) are requested in the prompt but `validate_analysis_output` does not yet require/normalize them — per the plan that validation belongs to Task 6.
