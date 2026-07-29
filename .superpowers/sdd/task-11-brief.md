### Task 11: heuristic 降级去污染

**Files:**
- Modify: `framework/stages/analyze.py:668-775`（`generate_heuristic_analysis`）

**Interfaces:**
- Consumes: 无
- Produces: heuristic 分析 dict 的 `opportunities` 恒为 `[]`，主观字段恒为 `''`

- [ ] **Step 1: 写失败验证**

```bash
PYTHONPATH=. python3 -c "
from framework.stages.analyze import generate_heuristic_analysis
a = generate_heuristic_analysis({'description': 'llm inference engine', 'topics': '[]'})
assert a['opportunities'] == [], a['opportunities']
assert a['problem_solved'] == '', a['problem_solved']
assert a['tech_layer'] == 'inference_engine', a['tech_layer']  # 分类职能保留
print('heuristic OK')
"
```

Expected: FAIL — 当前返回模板化 opportunities 和非空 problem_solved

- [ ] **Step 2: 改造返回 dict**

`generate_heuristic_analysis` 中：

1. 删除整段 `# Generate opportunities based on project type`（analyze.py:708-762 的 opportunities 构造），替换为：

```python
    # Heuristic path provides classification only. Subjective narrative fields
    # stay empty and no opportunities are fabricated (LLM path owns those).
```

2. 返回 dict（analyze.py:764-775）改为：

```python
    return {
        'tech_layer': tech_layer,
        'application': application,
        'problem_solved': '',
        'innovation_summary': '',
        'differentiation': '',
        'market_timing': '',
        'ecosystem_position': 'application_layer' if tech_layer == 'ai_application' else ('base_layer' if tech_layer in ('foundation_model', 'training_framework') else 'middleware'),
        'commercialization_path': '',
        'overall_score': min(10, max(1, 5 + int(float(((project.get('burst_signals') or {}).get('overall_score') or 0)) * 5))),
        'opportunities': []
    }
```

- [ ] **Step 3: 重跑 Step 1 验证 + 无 LLM 端到端（spec §4 验证项 5）**

```bash
python3 framework/stages/analyze.py --date $(date -u +%Y-%m-%d) --max-tasks 1
sqlite3 data/framework.db "SELECT analyzer_version, problem_solved FROM analyses ORDER BY id DESC LIMIT 1;"
```

Expected: 验证脚本输出 `heuristic OK`；若有 pending 任务被处理，最新分析行 `analyzer_version='heuristic-v1'` 且 `problem_solved` 为空

- [ ] **Step 4: Commit**

```bash
git add framework/stages/analyze.py
git commit -m "fix: heuristic analysis no longer fabricates opportunities or narratives"
```

