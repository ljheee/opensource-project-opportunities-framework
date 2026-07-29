# Task 11 Report: heuristic 降级去污染

## What was implemented

Modified `generate_heuristic_analysis` in `framework/stages/analyze.py` exactly as the
brief specifies:

1. Deleted the entire `# Generate opportunities based on project type` block (the
   templated opportunities: "LangChain/LlamaIndex Integration", "Managed API Service",
   "Enterprise Features", "Plugin Marketplace", "Performance Optimizations") and
   replaced it with the two-line comment from the brief.
2. Rewrote the return dict: `problem_solved`, `innovation_summary`, `differentiation`,
   `market_timing`, `commercialization_path` are now `''`; `opportunities` is now `[]`.
   `tech_layer`, `application`, `ecosystem_position`, and the burst-signal-derived
   `overall_score` are unchanged (classification function preserved).

## TDD evidence

### RED — Step 1 (before change)

```
$ PYTHONPATH=. python3 -c "
from framework.stages.analyze import generate_heuristic_analysis
a = generate_heuristic_analysis({'description': 'llm inference engine', 'topics': '[]'})
assert a['opportunities'] == [], a['opportunities']
..."
Traceback (most recent call last):
  File "<string>", line 4, in <module>
AssertionError: [{'opportunity_type': 'tech', 'title': 'Performance Optimizations',
'description': 'Benchmark and optimize for production workloads', ...}]
```

Failed as expected on the templated `opportunities`.

### GREEN — Step 1 re-run (after change)

```
heuristic OK
```

### GREEN — Step 3 end-to-end (no LLM, real DB)

The brief's verbatim command `--date $(date -u +%Y-%m-%d)` (2026-07-28) found no tasks,
because the 5 pending tasks in the DB all have `task_date=2026-04-26`. Since pending
tasks exist, I ran the live verification against their date (no tasks were created):

```
$ env -u USE_LLM python3 framework/stages/analyze.py --date 2026-04-26 --max-tasks 1
=== Stage 4: Deep Analysis ===
Found 1 tasks to analyze

Analyzing: lucidrains/vit-pytorch
  Using heuristic analysis (LLM unavailable)
  Analyzed: 0 opportunities found

Analyzed 1 projects, found 0 opportunities

$ sqlite3 data/framework.db "SELECT analyzer_version, problem_solved FROM analyses ORDER BY id DESC LIMIT 1;"
heuristic-v1|
```

Latest analysis row: `analyzer_version='heuristic-v1'`, `problem_solved` empty,
0 opportunities stored — matches the brief's expected outcome.

## Files changed

- `framework/stages/analyze.py` (8 insertions, 61 deletions) — commit `6765e3e`

## Self-review findings

- Diff matches the brief's Step 2 verbatim (comment text and return dict).
- `validate_analysis_output` (analyze.py:471) checks field *presence* only, not
  non-emptiness, and applies to the LLM path; empty strings do not break it.
- Storage layer (`analysis.get('problem_solved') or ''`, analyze.py:321) tolerates
  empty strings; the `analyses` table columns are plain `TEXT` with no NOT NULL
  constraint on narrative fields.
- Classification still verified by the Step 1 assertion
  (`tech_layer == 'inference_engine'`).

## Concerns

- The live Step 3 run processed one real pending task (`lucidrains/vit-pytorch`,
  task_date 2026-04-26) and mutated `data/framework.db` (task marked done, project
  status advanced, one analysis row inserted). Per the brief's Step 4, only
  `analyze.py` was committed; the DB change is left uncommitted in the working tree
  for the normal entry-script flow (`run.sh`) to checkpoint/commit.
- The brief's verbatim Step 3 command uses today's date, under which no pending tasks
  exist; the live verification required targeting the actual task_date of existing
  pending tasks. Flagging in case the intended semantic was "today only".
