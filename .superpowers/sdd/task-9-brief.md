### Task 9: analyze.py README 抓取与清洗

**Files:**
- Modify: `framework/stages/analyze.py`（imports 区、`get_project_data`）

**Interfaces:**
- Consumes: 环境变量 `GITHUB_TOKEN`（与 discover.py 同款）
- Produces: `_fetch_readme(project_id: str) -> str` — 清洗后 ≤10000 字符的 README 文本，失败返回 `''`；`get_project_data` 返回的 dict 增加 `readme` 键

- [ ] **Step 1: 写失败验证**

```bash
PYTHONPATH=. python3 -c "
from framework.stages.analyze import _fetch_readme
text = _fetch_readme('octocat/Hello-World')
assert isinstance(text, str) and len(text) > 0, 'empty readme'
assert len(text) <= 10000, len(text)
print('readme OK,', len(text), 'chars')
"
```

Expected: FAIL — `ImportError: cannot import name '_fetch_readme'`

- [ ] **Step 2: 实现抓取与清洗**

analyze.py imports 区（第 13 行 `import subprocess` 后）追加：

```python
import requests
```

模块级（`VALID_TIME_HORIZONS` 常量之后）追加：

```python
_GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
_README_HEADERS = {'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}
if _GITHUB_TOKEN:
    _README_HEADERS['Authorization'] = f'Bearer {_GITHUB_TOKEN}'

_README_MAX_CHARS = 10000
_DATA_URI_RE = re.compile(r'!\[[^\]]*\]\(\s*data:[^)]*\)', re.IGNORECASE)
_IMG_TAG_RE = re.compile(r'<(img|picture|source)[^>]*>.*?</\1>|<(img|source)[^>]*/?>', re.IGNORECASE | re.DOTALL)
_BADGE_RE = re.compile(r'\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)')


def _sanitize_readme(text: str) -> str:
    """Strip base64 data URIs, img/picture tags, and badge links before truncation."""
    text = _DATA_URI_RE.sub('', text)
    text = _IMG_TAG_RE.sub('', text)
    text = _BADGE_RE.sub('', text)
    return text[:_README_MAX_CHARS]


def _fetch_readme(project_id: str) -> str:
    """Fetch and sanitize a repo's README. Returns '' on any failure."""
    try:
        r = requests.get(
            f"https://api.github.com/repos/{project_id}/readme",
            headers=_README_HEADERS, timeout=30
        )
        if r.status_code != 200:
            print(f"  README fetch failed for {project_id}: HTTP {r.status_code}")
            return ''
        import base64
        raw = base64.b64decode(r.json().get('content') or '')
        return _sanitize_readme(raw.decode('utf-8', errors='replace'))
    except Exception as e:
        print(f"  README fetch error for {project_id}: {e}")
        return ''
```

`get_project_data` 中 `proj_dict['peers'] = ...`（analyze.py:192-198）之后追加：

```python
        proj_dict['readme'] = _fetch_readme(project_id)
```

- [ ] **Step 3: 重跑 Step 1 验证 + 清洗验证**

```bash
PYTHONPATH=. GITHUB_TOKEN=$(grep GITHUB_TOKEN .env | cut -d= -f2 | tr -d '"') python3 -c "
from framework.stages.analyze import _fetch_readme, _sanitize_readme
dirty = '![x](data:image/png;base64,AAAA) <img src=\"data:image/png;base64,BBBB\"> [![b](https://img.shields.io/x)](https://y) real content'
clean = _sanitize_readme(dirty)
assert 'data:' not in clean and 'shields.io' not in clean and 'real content' in clean, clean
text = _fetch_readme('huggingface/transformers')
assert 100 < len(text) <= 10000, len(text)
assert 'base64' not in text.lower() or 'base64' in text.lower()  # 内容词不强制
print('sanitize + fetch OK,', len(text), 'chars')
"
```

Expected: 输出 `sanitize + fetch OK`

- [ ] **Step 4: Commit**

```bash
git add framework/stages/analyze.py
git commit -m "feat: fetch and sanitize repo README for analysis input"
```

