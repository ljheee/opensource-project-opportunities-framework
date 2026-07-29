# SDD Progress: discovery-analysis-fixes
Plan: docs/superpowers/plans/2026-07-28-discovery-analysis-fixes.md
Branch: fix/discovery-analysis
Pre-existing changes committed: 03f388a

## Tasks
Task 1: complete (commits 03f388a..a4dbded, review clean)
Task 2: complete (commits a4dbded..fbfa45a, review clean)
Task 3: complete (commits fbfa45a..0d829e5, review clean)
Task 4: complete (commits 0d829e5..3a80f0c, review clean)
Task 5: complete (commits 3a80f0c..1fe0561, review clean)
Task 6: complete (commits 1fe0561..2b980b4, review clean)
Task 7: complete (commits 2b980b4..32f5c59, review clean)
Task 8: complete (commits 32f5c59..0abc4ea, review clean) — PHASE 1 DONE
Task 9: complete (commits 0abc4ea..c83cac0, review clean)
Task 10: complete (commits c83cac0..0e99a16, review clean)
Task 11: complete (commits 0e99a16..6765e3e, review clean); live verify marked lucidrains/vit-pytorch task done in DB (uncommitted, normal flow)
Task 12: complete (commits 6765e3e..0803ae5, review clean); brief defect #4 already fixed in 0944997
Task 13: complete (commits 0803ae5..b66b402, review clean) — ALL 13 TASKS DONE
Final review: complete (verdict "With fixes" — 1 Important fixed + re-reviewed clean)
Final fixes: complete (commits b66b402..93bf278, re-review approved)
Remaining for user/CI: V1/V5 full pipeline runs (push to remote, multi-day), V2 rate-limit measurement, V3 LLM analysis, V6/V7 post-deploy observations

## Minor findings (for final review)
- Task 13: (1) staged-NEW data files (e.g. first-ever framework.db) survive checkout HEAD -- data/ — pull --rebase would fail dirty-index, bounded impact (end-of-run add+commit picks it up); (2) "[0/6] git pull..." prints before abort (cosmetic)
- Task 12: (1) negative config values not clamped (could starve all analyzed projects); (2) growth window is "latest sample at/before 7d ago", not strictly 7d (spec-inherited); (3) NULL last_commit_at falls through silently (correct but uncommented)
- Task 11: brief Step 3 command is date-brittle (works only when today has pending tasks)
- Task 10: dead else-branch analyzer_version assignment (plan-mandated verbatim, cosmetic cleanup later)
- Task 9: sanitize runs on full untruncated README (~1MB worst case, linear-safe); heuristic path now also fetches README (1 API call/project, plan-mandated); import base64 in function body cosmetic
- Task 8: none material (bucket header cosmetic; git identity note applies repo-wide)
- Task 7: (1) _fn_threshold() called per-row in loop (cheap but inconsistent); (2) --min-days flag does not flow to min_days_for_fn; (3) recall denominator mixes all-source TP with trending-only FN (approximation, from implementer)
- Task 6: fetch_outcomes still selects/coerces unused community_buzz_at_pred column (spec-sanctioned, future cleanup)
- Task 5: sampling truncation at 100 commits + no contributor refresh (both plan-mandated); redundant or {} cosmetic
- Task 4: (1) permanently-failing repos re-attempt backfill every run (no failure memo); (2) single-day backfill equal to today re-triggers once, self-heals; (3) synthetic_history flag ages out after 35d window (spec-acknowledged)
- Task 3: (1) timestamps appended before ISO validation — malformed starred_at could break pure-date invariant; (2) written counts attempts not inserted rows (unreachable today); (3) cutoff uses strict < so exactly-35d page fetches one more page (harmless); (4) covered>stars case ends curve above actual (spec-acknowledged territory)
- Task 2: cutoff recomputed per loop iteration / req_headers rebuilt per retry (both plan-mandated, negligible); stale-repo side effect of sort=updated mitigated by existing 180d filter
- Task 1: get_backfill_config closure _pos_int could hoist if a 3rd key appears; 36/712 one-time early-burst promotions expected on next discover run
