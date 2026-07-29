# Task 6 Report: 证据成员校验 + evidence_json 存储

> Note: this file previously contained a stale report from an unrelated earlier "Task 6" (reweight.py buzz removal, commit 2b980b4, different plan). Overwritten per team-lead instruction to use this path.

**Status:** DONE
**Commit:** 3228810 feat: deterministic evidence membership validation and evidence_json storage

## What was implemented

All in `framework/stages/analyze.py`:

1. **`_evidence_matches(text, candidates)`** — case-insensitive substring membership helper.
2. **`_validate_evidence(analysis, structure)`** — deterministic hallucination guard:
   - `innovation_evidence` items must mention a `core_paths` file (full path or basename); `problem_evidence` items must mention a real `top_issues` title (titles < 8 chars excluded from the reference set).
   - No reference set (empty core_paths / empty usable titles, e.g. partial/no_match/uncollected structure) → ALL items of that kind stripped, `unverifiable_*` recorded in meta (conservative design: unverifiable evidence is NOT passed through).
   - Stripped-to-empty non-empty list → `confidence='low'` + dimension appended to `cannot_determine` (`innovation_summary` / `problem_solved`).
   - Returns `(cleaned_analysis, meta)` with `stripped_innovation` / `stripped_problem` counts.
3. **Format validation in `validate_analysis_output`** — inserted before the `# Ensure opportunities is a list` block: coerces `innovation_evidence`/`problem_evidence`/`cannot_determine` to `[]` when not lists; `confidence` not in {high, medium, low} → `'medium'`.
4. **Validation chain wiring in `generate_analysis_with_llm`** — after the `validate_analysis_output` success branch, before `return analysis`: `_validate_evidence(analysis, project.get('structure'))`, then `analysis['_evidence_meta'] = evidence_meta`. The private key rides on the analysis dict; the INSERT's explicit column list keeps it out of the DB.
5. **`store_analysis_and_opportunities`** — new `evidence: Optional[Dict] = None` param; INSERT column list gains `evidence_json`, bound as `json.dumps(evidence, ensure_ascii=False) if evidence else None`.
6. **`run_analysis`** — builds the evidence dict only when `analyzer_version == 'llm-v1'` (`innovation_evidence`, `problem_evidence`, `confidence` default 'medium', `cannot_determine`, `validation` from `_evidence_meta` default `{}`), passes it to the store call. Heuristic path stores NULL.

## TDD evidence

### RED (Step 1, before implementation)

```
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
ImportError: cannot import name '_validate_evidence' from 'framework.stages.analyze' (/Users/lijianhua04/Documents/my-agents/catpawDesk-workspace/github-opportunities/opensource-project-opportunities-framework/framework/stages/analyze.py)
```

### GREEN (Step 5, after implementation)

```
evidence validation OK
compile OK
```

### Additional smoke tests (beyond brief, same session)

- `PRAGMA table_info(analyses)` on live `data/framework.db`: `13|evidence_json|TEXT|0||0` — Task 1 migration column confirmed present.
- Fresh-schema end-to-end store test (temp DB via `db.init_tables()`): llm-v1 row persisted `evidence_json` with correct `confidence`/`validation`; heuristic-v1 row persisted NULL. Output: `store evidence smoke OK`.

## Files changed

- `framework/stages/analyze.py` (+88 / -5), commit 3228810. Only this file was staged/committed; pre-existing dirty `.superpowers/sdd/*` and `data/framework.db` changes from other agents were left untouched.

## Self-review findings

- Brief code applied verbatim; placement anchors matched the current file (`validate_analysis_output` at :495, retry-loop validation call in `generate_analysis_with_llm`, store call in `run_analysis`).
- `_evidence_meta` cannot leak into `analyses` — the INSERT uses an explicit column list.
- `run_analysis` reaches the store with `analyzer_version == 'llm-v1'` only when `generate_analysis_with_llm` returned non-None, so `_evidence_meta` is always set there; `.get(...) or {}` guards anyway.
- Heuristic path (`heuristic-v1`) stores NULL evidence_json — verified in smoke test.

## Concerns

None blocking. Minor observation (by design, not changed): issue titles shorter than 8 chars are excluded from the problem-evidence reference set, so a project whose only top issues have very short titles behaves like "no reference set" for problem evidence (all problem evidence stripped as unverifiable). This matches the brief's deliberate conservative semantics.
