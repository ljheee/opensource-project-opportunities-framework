### Task 6: 证据成员校验 + evidence_json 存储

**Files:**
- Modify: `framework/stages/analyze.py`（`validate_analysis_output`、新增 `_validate_evidence`、`generate_analysis_with_llm` 校验链、`run_analysis`/`store_analysis_and_opportunities`）

**Interfaces:**
- Consumes: `get_project_data` 的 `structure`（core_paths、top_issues）
- Produces: `_validate_evidence(analysis: Dict, structure: Optional[Dict]) -> Tuple[Dict, Dict]` — 返回（清洗后 analysis, validation 元信息 `{'stripped_innovation': int, 'stripped_problem': int}`）；`store_analysis_and_opportunities(..., evidence: Optional[Dict] = None)` 写 `analyses.evidence_json`

- [ ] **Step 1: 写失败验证**

```bash
PYTHONPATH=. python3 - <<'EOF'
from framework.stages.analyze import _validate_evidence
structure = {'core_paths': ['src/engine.py'], 'top_issues': [{'title': 'OOM on batch', 'comments': 9, 'reactions': 40}]}
analysis = {
    'innovation_evidence': ['src/engine.py uses flash attention', 'src/imaginary.py does magic'],
    'problem_evidence': ['users report "OOM on batch" with 40 reactions', 'issue #99999 about nothing'],
    'confidence': 'high',
    'cannot_determine': [],
}
cleaned, meta = _validate_evidence(analysis, structure)
assert cleaned['innovation_evidence'] == ['src/engine.py uses flash attention'], cleaned
assert cleaned['problem_evidence'] == ['users report "OOM on batch" with 40 reactions'], cleaned
assert cleaned['confidence'] == 'high'
assert meta == {'stripped_innovation': 1, 'stripped_problem': 1}, meta
# 全剔光 → confidence 强制 low + cannot_determine 补维度
analysis2 = {'innovation_evidence': ['fake/file.py x'], 'problem_evidence': [], 'confidence': 'high', 'cannot_determine': []}
c2, m2 = _validate_evidence(analysis2, structure)
assert c2['innovation_evidence'] == [] and c2['confidence'] == 'low'
assert 'innovation_summary' in c2['cannot_determine'], c2
# 无参考集（partial/no_match）→ 不放行，记 unverifiable
c3, m3 = _validate_evidence(
    {'innovation_evidence': ['anything.py does x'], 'problem_evidence': [], 'confidence': 'high', 'cannot_determine': []},
    {'core_paths': [], 'top_issues': []})
assert c3['innovation_evidence'] == [] and c3['confidence'] == 'low'
assert m3.get('unverifiable_innovation') == 1, m3
print('evidence validation OK')
EOF
```

Expected: FAIL — `ImportError: cannot import name '_validate_evidence'`

- [ ] **Step 2: 实现成员校验**

`validate_analysis_output` 之后插入：

```python
def _evidence_matches(text: str, candidates: List[str]) -> bool:
    """True if any candidate token appears in the evidence string."""
    low = text.lower()
    return any(c.lower() in low for c in candidates if c)


def _validate_evidence(analysis: Dict, structure: Optional[Dict]) -> Tuple[Dict, Dict]:
    """Deterministic membership check for LLM-cited evidence (hallucination guard).

    - innovation_evidence items must mention a file from core_paths (or its basename)
    - problem_evidence items must mention a real top_issues title (substring)
    - stripped-to-empty innovation list -> confidence='low' + 'innovation_summary'
      appended to cannot_determine (same for problem_solved)
    Returns (cleaned_analysis, validation_meta).
    """
    cleaned = dict(analysis)
    structure = structure or {}
    core_paths = structure.get('core_paths') or []
    file_tokens = list(core_paths) + [p.rsplit('/', 1)[-1] for p in core_paths if '/' in p]
    issue_titles = [(t.get('title') or '') for t in (structure.get('top_issues') or [])]
    title_tokens = [t for t in issue_titles if len(t) >= 8]

    inno = cleaned.get('innovation_evidence') or []
    prob = cleaned.get('problem_evidence') or []
    cd = cleaned.get('cannot_determine') or []
    if not isinstance(cd, list):
        cd = []
    cd = list(cd)
    meta = {'stripped_innovation': 0, 'stripped_problem': 0}

    # 无参考集（partial/no_match/未采集）时无法验证 → 一律剔除并降级，
    # 与"幻觉引用不放行"的保守方向一致（review 修正：原设计放行）
    if file_tokens:
        kept_inno = [e for e in inno if isinstance(e, str) and _evidence_matches(e, file_tokens)]
        meta['stripped_innovation'] = len(inno) - len(kept_inno)
    else:
        kept_inno = []
        if inno:
            meta['unverifiable_innovation'] = len(inno)
    if title_tokens:
        kept_prob = [e for e in prob if isinstance(e, str) and _evidence_matches(e, title_tokens)]
        meta['stripped_problem'] = len(prob) - len(kept_prob)
    else:
        kept_prob = []
        if prob:
            meta['unverifiable_problem'] = len(prob)
    cleaned['innovation_evidence'] = kept_inno
    cleaned['problem_evidence'] = kept_prob

    if inno and not kept_inno:
        cleaned['confidence'] = 'low'
        if 'innovation_summary' not in cd:
            cd.append('innovation_summary')
    if prob and not kept_prob:
        cleaned['confidence'] = 'low'
        if 'problem_solved' not in cd:
            cd.append('problem_solved')
    cleaned['cannot_determine'] = cd
    return cleaned, meta
```

- [ ] **Step 3: `validate_analysis_output` 加格式校验**

在 `# Ensure opportunities is a list` 段之前插入：

```python
    # Evidence contract fields (format only; membership checked by _validate_evidence)
    for field in ('innovation_evidence', 'problem_evidence', 'cannot_determine'):
        if not isinstance(cleaned.get(field), list):
            cleaned[field] = []
    if cleaned.get('confidence') not in ('high', 'medium', 'low'):
        cleaned['confidence'] = 'medium'
```

- [ ] **Step 4: 校验链接线 + 存储**

(a) `generate_analysis_with_llm` 中 `valid, error, analysis = validate_analysis_output(analysis)` 之后、`return analysis` 之前插入：

```python
                analysis, evidence_meta = _validate_evidence(analysis, project.get('structure'))
                analysis['_evidence_meta'] = evidence_meta
```

（注意：`run_analysis` 调用点在循环内，`project` 在作用域内可用——`generate_analysis_with_llm(project, ...)` 的第一个参数即是。）

(b) `store_analysis_and_opportunities` 签名加 `evidence: Optional[Dict] = None`；INSERT 列清单加 `evidence_json`，参数加 `json.dumps(evidence, ensure_ascii=False) if evidence else None`。

(c) `run_analysis` 中 store 调用改为：

```python
            evidence = None
            if analyzer_version == 'llm-v1':
                evidence = {
                    'innovation_evidence': analysis.get('innovation_evidence') or [],
                    'problem_evidence': analysis.get('problem_evidence') or [],
                    'confidence': analysis.get('confidence') or 'medium',
                    'cannot_determine': analysis.get('cannot_determine') or [],
                    'validation': analysis.get('_evidence_meta') or {},
                }
            opportunities_count = store_analysis_and_opportunities(
                db, project_id, analysis, conn=conn, analyzer_version=analyzer_version,
                evidence=evidence
            )
```

- [ ] **Step 5: 重跑 Step 1 验证 + py_compile**

```bash
PYTHONPATH=. python3 -c "import py_compile; py_compile.compile('framework/stages/analyze.py', doraise=True); print('compile OK')"
```

Expected: Step 1 输出 `evidence validation OK`；compile OK

- [ ] **Step 6: Commit**

```bash
git add framework/stages/analyze.py
git commit -m "feat: deterministic evidence membership validation and evidence_json storage"
```

