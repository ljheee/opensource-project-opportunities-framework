### Task 4: L2 输入组装（analyze.py 核心文件节选 + 骨架事实）

**Files:**
- Modify: `framework/stages/analyze.py`（`get_project_data`、新增 `_fetch_core_excerpts`）

**Interfaces:**
- Consumes: `projects.structure_json`（Task 3 写入）
- Produces: `get_project_data` 返回 dict 新增两键：`structure`（解析后的骨架事实 dict 或 None）、`core_excerpts`（`List[Dict]`，`[{'path', 'content'}]`，各 ≤5000 字符）；`_fetch_core_excerpts(project_id, core_paths) -> List[Dict]`；Task 5/6 消费

- [ ] **Step 1: 写失败验证**

```bash
PYTHONPATH=. python3 -c "
from framework.stages.analyze import _fetch_core_excerpts
out = _fetch_core_excerpts('psf/requests', ['src/requests/api.py'])
assert isinstance(out, list) and len(out) == 1, out
assert out[0]['path'] == 'src/requests/api.py' and 100 < len(out[0]['content']) <= 5000
assert 'def request' in out[0]['content'] or 'def get' in out[0]['content']
print('OK')
"
```

Expected: FAIL — `ImportError: cannot import name '_fetch_core_excerpts'`

- [ ] **Step 2: 实现 raw 抓取**

模块级（`_fetch_readme` 之后）追加：

```python
_CORE_EXCERPT_MAX = 5000


def _fetch_core_excerpts(project_id: str, core_paths: List) -> List[Dict]:
    """Fetch up to 3 core file excerpts via raw.githubusercontent.com (no API quota)."""
    excerpts = []
    for path in (core_paths or [])[:3]:
        if not isinstance(path, str) or not path:
            continue
        try:
            r = requests.get(
                f"https://raw.githubusercontent.com/{project_id}/HEAD/{path}",
                headers={'User-Agent': 'Mozilla/5.0'}, timeout=15
            )
            if r.status_code != 200:
                continue
            text = r.text
            if '\x00' in text[:8192]:
                continue  # binary
            excerpts.append({'path': path, 'content': text[:_CORE_EXCERPT_MAX]})
        except requests.exceptions.RequestException:
            continue
    return excerpts
```

`get_project_data` 中 `proj_dict['readme'] = _fetch_readme(project_id)` 之后追加：

```python
        structure = None
        raw_structure = proj_dict.get('structure_json')
        if raw_structure:
            try:
                structure = json.loads(raw_structure)
            except (json.JSONDecodeError, TypeError):
                structure = None
        proj_dict['structure'] = structure
        proj_dict['core_excerpts'] = _fetch_core_excerpts(
            project_id, (structure or {}).get('core_paths') or []
        )
```

- [ ] **Step 3: 重跑 Step 1 验证 + 空路径验证**

```bash
PYTHONPATH=. python3 -c "
from framework.stages.analyze import _fetch_core_excerpts
assert _fetch_core_excerpts('a/b', []) == []
assert _fetch_core_excerpts('a/b', None) == []
assert _fetch_core_excerpts('nonexistent-xyz/nope-xyz', ['main.py']) == []
print('edge cases OK')
"
```

Expected: 两个验证均通过

- [ ] **Step 4: Commit**

```bash
git add framework/stages/analyze.py
git commit -m "feat: assemble L2 analysis inputs (structure facts + core file excerpts)"
```

