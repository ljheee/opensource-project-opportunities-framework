### Task 8: report.py 展示 FN/TN 与 recall

**Files:**
- Modify: `framework/stages/report.py:70-88`（Validation metrics 计数区）、`144-177`（metrics 输出区）

**Interfaces:**
- Consumes: Task 7 写入的 `false_negative` / `true_negative` 行

- [ ] **Step 1: 计数区追加 FN/TN**

report.py:88 的 `fp_count` 计数块之后追加：

```python
            try:
                fn_count = int(conn.execute(
                    "SELECT COUNT(*) FROM prediction_outcomes WHERE outcome = 'false_negative'"
                ).fetchone()[0] or 0)
            except (ValueError, TypeError):
                fn_count = 0
            try:
                tn_count = int(conn.execute(
                    "SELECT COUNT(*) FROM prediction_outcomes WHERE outcome = 'true_negative'"
                ).fetchone()[0] or 0)
            except (ValueError, TypeError):
                tn_count = 0
```

- [ ] **Step 2: 输出区追加 recall（注意渲染条件）**

report.py:144 的渲染分支条件必须放宽——`total_evaluated` 只统计 TP/FP，FN 可能先于任何 TP/FP 成熟，不能藏在分支里。把：

```python
            if total_evaluated > 0:
```

改为：

```python
            if total_evaluated > 0 or (fn_count + tn_count) > 0:
```

并在该分支内 `avg_pred_fp` 输出行（report.py:177）之后追加：

```python
                lines.append(f"- **Missed bursts (FN):** {fn_count} | **Correctly passed (TN):** {tn_count}")
                if tp_count + fn_count > 0:
                    recall = tp_count / (tp_count + fn_count)
                    lines.append(f"- **Recall (trending-source):** {recall:.1%}")
```

（分支内其余语句均只依赖 total_evaluated，为 0 时跳过 precision 段不受影响——precision 段本身在 `if total_evaluated > 0` 语义下输出，保持原样即可；若 total_evaluated 为 0 时进入分支，precision 相关行会输出除零——因此需把 precision 四行（report.py:174-177）包在 `if total_evaluated > 0:` 内层判断里，FN/TN 行放在内层判断之外。）

- [ ] **Step 3: 验证**

```bash
python3 framework/stages/report.py --date $(date -u +%Y-%m-%d) && grep -A3 "Validation Metrics" data/reports/$(date -u +%Y-%m-%d).md | head -8
```

Expected: 报告正常生成；当前无 outcomes 数据显示 `_No predictions have matured enough for evaluation._`（不崩即通过）。可选择在 Task 7 的 /tmp/fn_test.db 验证通过后，临时指向该 DB 生成一次报告确认 FN 行渲染——非阻塞。

- [ ] **Step 4: Commit**

```bash
git add framework/stages/report.py
git commit -m "feat: report recall metrics (FN/TN) in daily report"
```

---

# Phase 2：分析端 + 工程杂项

