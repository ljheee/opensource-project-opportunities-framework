# Task 8 Report: report.py 展示 FN/TN 与 recall

## What I implemented

Two edits to `framework/stages/report.py`:

1. **Counting region** (after the `fp_count` block, ~line 88): added `fn_count` and `tn_count` try/except counting blocks exactly as specified in the brief (counting `false_negative` / `true_negative` rows in `prediction_outcomes`).

2. **Render region** (~line 158): widened the outer condition from `if total_evaluated > 0:` to `if total_evaluated > 0 or (fn_count + tn_count) > 0:`. Inside, wrapped the precision block in an inner `if total_evaluated > 0:` guard, and placed the FN/TN line plus the conditional recall line outside that inner guard, per the brief.

**One deliberate extension of the brief's literal text:** the brief's parenthetical named only the four precision output lines (old 174-177) for the inner guard. However, old line 145 `precision = tp_count / total_evaluated` also divides by `total_evaluated` and would raise `ZeroDivisionError` on the FN/TN-only path. I therefore wrapped the entire precision block (the `precision` calculation, the four `avg_*` queries that feed only the precision lines, and the four output lines) in the inner guard. This is the minimal change that makes the widened branch actually safe, matching the brief's stated intent ("precision 相关行会输出除零——因此需把 precision 四行包在 if total_evaluated > 0: 内层判断里").

The Score Bucket Calibration table remains in the outer branch unguarded: its query filters `outcome IN ('true_positive','false_positive')`, so with FN/TN-only data it returns zero rows and `if buckets:` suppresses output — verified safe.

## Verification evidence

### Brief Step 3 — real DB (0 outcome rows)

```
$ python3 framework/stages/report.py --date $(date -u +%Y-%m-%d) && grep -A3 "Validation Metrics" data/reports/$(date -u +%Y-%m-%d).md | head -8
Report generated: .../data/reports/2026-07-28.md
## Validation Metrics

_No predictions have matured enough for evaluation._
```

Fallback renders, no crash.

### FN/TN-only path (widened branch, no TP/FP)

`/tmp/fn_test.db` from Task 7 still existed with 1 `false_negative` row; added 1 `true_negative` row (id=2, project c/d). Then:

```
$ PYTHONPATH=. python3 -c "
from framework.core.db import Database
from framework.stages.report import ReportGenerator
db = Database('/tmp/fn_test.db')
ReportGenerator(db).generate('2026-07-28')
"
$ grep -A6 "Validation Metrics" /tmp/reports/2026-07-28.md
## Validation Metrics

- **Missed bursts (FN):** 1 | **Correctly passed (TN):** 1
- **Recall (trending-source):** 0.0%
```

No ZeroDivisionError; precision lines correctly suppressed; recall = 0/(0+1) = 0.0%.

### Mixed path (TP + FN + TN) — extra sanity check

Added 1 `true_positive` row (id=3, project e/f) to `/tmp/fn_test.db`, regenerated:

```
## Validation Metrics

- **Predictions evaluated:** 1 (TP: 1, FP: 0)
- **Precision (7d+ horizon):** 100.0%
- **Avg actual growth — TP:** 10.0 stars/day, FP: 0.0 stars/day
- **Avg predicted growth — TP:** 5.0 stars/day, FP: 0.0 stars/day
- **Missed bursts (FN):** 1 | **Correctly passed (TN):** 1
- **Recall (trending-source):** 50.0%

### Score Bucket Calibration
```

Inner precision block, FN/TN line, recall (1/(1+1)=50.0%), and bucket table all render correctly together.

## Files changed

- `framework/stages/report.py` (+51/-34), commit `0abc4ea` "feat: report recall metrics (FN/TN) in daily report" on branch `fix/discovery-analysis`.

## Self-review findings

- Diff matches the brief verbatim except the inner guard also covers the `precision = tp_count / total_evaluated` calculation and the four `avg_*` query blocks (they only feed the precision lines). Justified above; without it the FN/TN-only path crashes.
- FN/TN/recall lines sit outside the inner guard and before the bucket table, matching the brief's "append after avg_pred_fp line" intent.
- `git status` before commit showed only `framework/stages/report.py` modified; the regenerated `data/reports/2026-07-28.md` does not appear in git status (data dir handling unchanged).
- `/tmp/fn_test.db` now contains 3 outcome rows (FN, TN, TP) — leftover test artifact in /tmp only, not in the repo.

## Concerns

- Minor: commit was made with auto-derived git identity (`lijianhua04@MBP-...local`) because no user.email is configured; git warned but committed. Not amended since the brief did not ask for it and prior commits on the branch may share the same identity.
