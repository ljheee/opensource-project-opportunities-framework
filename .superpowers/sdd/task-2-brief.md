### Task 2: L1 采集器（`_fetch_structure_facts` 系列）

**Files:**
- Modify: `framework/stages/discover.py`（`DiscoverStage` 新增 4 个方法，插在 `_fetch_weekly_contributors` 之后）

**Interfaces:**
- Consumes: `_github_request(...)`（已有）、`ConfigLoader.get_filters()`（已有）
- Produces: `_fetch_structure_facts(full_name: str) -> Optional[Dict]` — 返回不含 `fetched_at` 的骨架事实 dict（结构见 Step 5），整体失败返回 None；Task 3 挂载时调用

- [ ] **Step 1: 写失败验证**

```bash
PYTHONPATH=. python3 -c "
from framework.core.config_loader import ConfigLoader
from framework.core.db import Database
from framework.stages.discover import DiscoverStage
s = DiscoverStage(ConfigLoader(), Database())
assert hasattr(s, '_fetch_structure_facts'), 'method missing'
print('OK')
"
```

Expected: FAIL — `AssertionError: method missing`

- [ ] **Step 2: 实现树解析与 core_paths 选取**

```python
    _SRC_EXTS = ('.py', '.ts', '.tsx', '.rs', '.go', '.ipynb')
    _GEN_PATTERNS = ('_pb2.py', '.min.js', '.pb.go', '_pb2_grpc.py')
    _CORE_DIRS = ('src/', 'core/', 'lib/', 'internal/', 'cmd/')
    _CORE_KEYWORDS = ('model', 'inference', 'engine', 'agent', 'server')
    _ENTRY_NAMES = ('main', 'app', 'cli', 'server', 'mod', 'index')

    def _select_core_paths(self, paths: List[Dict]) -> Tuple[List[str], Optional[str]]:
        """Pick up to 3 core source files from tree entries [{path, size}].
        Two layers: (1) keyword match under core dirs; (2) entry-file fallback.
        Returns (core_paths, reason) — reason is None, 'no_match'.
        Skips >100KB files and generated-code patterns.
        """
        def _ok(entry):
            p = entry.get('path') or ''
            if not p.lower().endswith(self._SRC_EXTS):
                return False
            if (entry.get('size') or 0) > 100 * 1024:
                return False
            name = p.rsplit('/', 1)[-1].lower()
            return not any(name.endswith(g) for g in self._GEN_PATTERNS)

        candidates = [e for e in paths if _ok(e)]
        # Layer 1: keyword match under core dirs
        layer1 = []
        for e in candidates:
            p = e['path'].lower()
            if any(p.startswith(d) or f'/{d}' in p for d in self._CORE_DIRS):
                if any(k in p for k in self._CORE_KEYWORDS):
                    layer1.append(e['path'])
        if layer1:
            return sorted(layer1)[:3], None
        # Layer 2: entry files at root or src/
        layer2 = []
        for e in candidates:
            p = e['path']
            parts = p.split('/')
            name = parts[-1].rsplit('.', 1)[0].lower()
            if len(parts) == 1 and name in self._ENTRY_NAMES:
                layer2.append(p)
            elif p in ('src/main.rs', 'src/lib.rs', 'src/main.py', 'src/app.py'):
                layer2.append(p)
        if layer2:
            return sorted(layer2)[:3], None
        return [], 'no_match'

    def _parse_tree(self, tree_entries: List[Dict], partial: bool) -> Dict:
        """Extract structural facts from tree entries."""
        paths = [e for e in tree_entries if isinstance(e, dict) and e.get('type') == 'blob']
        # 目录条目（type='tree'）也要收集：根目录降级（partial）路径下，
        # 目录存在性判断完全依赖它们（review 修正：只收 blob 会导致
        # partial 时 has_tests/has_docs 等恒为 False）
        root_dirs = {e['path'].lower() for e in tree_entries
                     if isinstance(e, dict) and e.get('type') == 'tree' and '/' not in (e.get('path') or '')}
        all_paths = [e.get('path') or '' for e in paths]
        dirs = {p.split('/')[0].lower() for p in all_paths if p} | root_dirs
        facts = {
            'has_tests': any(d in dirs for d in ('tests', 'test')) or any(p.lower().startswith(('tests/', 'test/')) for p in all_paths),
            'has_ci': any(p.lower().startswith('.github/workflows/') for p in all_paths),
            'has_docs': 'docs' in dirs or 'doc' in dirs,
            'has_examples': 'examples' in dirs or 'example' in dirs,
            'partial': partial,
        }
        core_paths, reason = self._select_core_paths(paths)
        facts['core_paths'] = [] if partial else core_paths
        facts['core_paths_reason'] = 'partial' if partial else reason
        # Manifest path: first hit by ecosystem-agnostic priority
        manifest = None
        for name in ('pyproject.toml', 'requirements.txt', 'package.json', 'Cargo.toml', 'go.mod'):
            if name in all_paths:
                manifest = name
                break
        facts['_manifest_path'] = manifest
        return facts
```

- [ ] **Step 3: 实现清单与 issues 抓取**

```python
    def _fetch_manifest_deps(self, full_name: str, manifest_path: Optional[str]) -> Tuple[List[str], List[str]]:
        """Fetch dependency manifest via raw (no API quota). Returns (deps, matched)."""
        if not manifest_path:
            return [], []
        try:
            r = requests.get(
                f"https://raw.githubusercontent.com/{full_name}/HEAD/{manifest_path}",
                headers={'User-Agent': 'Mozilla/5.0'}, timeout=15
            )
            if r.status_code != 200:
                return [], []
            text = r.text[:200 * 1024]
        except requests.exceptions.RequestException:
            return [], []
        deps: List[str] = []
        if manifest_path == 'package.json':
            try:
                pkg = json.loads(text)
                deps = sorted(set(list((pkg.get('dependencies') or {}).keys())
                                + list((pkg.get('devDependencies') or {}).keys())))
            except (json.JSONDecodeError, TypeError):
                deps = []
        elif manifest_path in ('Cargo.toml', 'pyproject.toml'):
            in_deps = False
            array_continues = False
            for line in text.splitlines():
                ls = line.strip()
                if ls.startswith('[') and ls.endswith(']') and '=' not in ls:
                    # 段头：[dependencies] / [project] / [tool.poetry.dependencies] 等
                    in_deps = 'dependencies' in ls and 'optional-dependencies' not in ls and 'dev-dependencies' not in ls
                    array_continues = False
                    continue
                if in_deps:
                    # PEP 621: [project] 段内 dependencies = ["a", "b"] 可能跨行
                    if ls.startswith('dependencies') and '=' in ls:
                        array_continues = '[' in ls and ']' not in ls
                        names = re.findall(r'"([A-Za-z0-9_.-]+)"', ls)
                        deps.extend(names)
                        continue
                    if array_continues:
                        names = re.findall(r'"([A-Za-z0-9_.-]+)"', ls)
                        deps.extend(names)
                        if ']' in ls:
                            array_continues = False
                        continue
                    if ls and not ls.startswith('#') and '=' in ls:
                        name = re.split(r'[\s=\[("\'><~^]', ls, maxsplit=1)[0].strip().strip('"\'')
                        if name and re.match(r'^[A-Za-z0-9_.-]+$', name) and name != 'dependencies':
                            deps.append(name)
        elif manifest_path == 'go.mod':
            for line in text.splitlines():
                ls = line.strip()
                if not ls or ls.startswith('//'):
                    continue
                first = ls.split()[0] if ls.split() else ''
                if first in ('module', 'go', 'require', 'replace', 'exclude', ')', '('):
                    continue
                name = first.strip()
                if name and re.match(r'^[A-Za-z0-9_./-]+$', name):
                    deps.append(name)
        else:  # requirements.txt
            for line in text.splitlines():
                ls = line.strip()
                if not ls or ls.startswith(('#', '-')):
                    continue
                name = re.split(r'[\s=><~^(;]', ls, maxsplit=1)[0].strip()
                if name and re.match(r'^[A-Za-z0-9_.-]+$', name):
                    deps.append(name)
        eco = self.config.get_filters().get('known_ecosystem_packages', [])
        if not isinstance(eco, list):
            eco = []
        eco_set = {str(p).lower() for p in eco}
        matched = sorted({d for d in deps if d.lower() in eco_set})
        return deps[:200], matched

    def _fetch_issue_health(self, full_name: str) -> Tuple[Optional[Dict], List[Dict]]:
        """Top-comment issues (PRs filtered out). Returns (issue_health, top_issues)."""
        try:
            repo = self._github_request(f"https://api.github.com/repos/{quote(full_name, safe='/')}")
            if repo.get('has_issues') is False:
                return None, []
            items = self._github_request(
                f"https://api.github.com/repos/{quote(full_name, safe='/')}/issues",
                params={"state": "all", "sort": "comments", "direction": "desc", "per_page": 10},
            )
        except GitHubAPIError as e:
            print(f"  Issue health fetch failed for {full_name}: {e}")
            return None, []
        if not isinstance(items, list):
            return None, []
        issues = [i for i in items if isinstance(i, dict) and 'pull_request' not in i]
        total_reactions = 0
        total_comments = 0
        active_30d = 0
        now = datetime.now(timezone.utc)
        for i in issues:
            total_reactions += int(((i.get('reactions') or {}).get('total_count') or 0))
            total_comments += int(i.get('comments') or 0)
            upd = i.get('updated_at') or ''
            try:
                if (now - datetime.fromisoformat(upd.replace('Z', '+00:00'))).days <= 30:
                    active_30d += 1
            except (ValueError, TypeError):
                pass
        health = {
            'reaction_total': total_reactions,
            'avg_comments': round(total_comments / len(issues), 1) if issues else 0.0,
            'active_issues_30d': active_30d,
            'issue_count': len(issues),
        }
        top = [{'title': (i.get('title') or '')[:200],
                'comments': i.get('comments') or 0,
                'reactions': int(((i.get('reactions') or {}).get('total_count') or 0))}
               for i in issues[:5]]
        return health, top
```

- [ ] **Step 4: 实现主编排方法**

```python
    def _fetch_structure_facts(self, full_name: str) -> Optional[Dict]:
        """Collect L1 structural facts for a repo. None on total failure."""
        try:
            tree_resp = self._github_request(
                f"https://api.github.com/repos/{quote(full_name, safe='/')}/git/trees/HEAD",
                params={"recursive": "1"},
            )
        except GitHubAPIError as e:
            print(f"  Tree fetch failed for {full_name}: {e}")
            return None
        entries = tree_resp.get('tree') if isinstance(tree_resp, dict) else None
        if not isinstance(entries, list):
            return None
        partial = bool(tree_resp.get('truncated'))
        if partial:
            # Never treat a truncated tree as complete: fall back to root listing
            try:
                root_resp = self._github_request(
                    f"https://api.github.com/repos/{quote(full_name, safe='/')}/git/trees/HEAD"
                )
                root_entries = root_resp.get('tree') if isinstance(root_resp, dict) else None
                if isinstance(root_entries, list):
                    entries = root_entries
            except GitHubAPIError:
                pass
        facts = self._parse_tree(entries, partial)
        deps, matched = self._fetch_manifest_deps(full_name, facts.pop('_manifest_path'))
        facts['dependencies'] = deps
        facts['matched_ecosystem_packages'] = matched
        health, top = self._fetch_issue_health(full_name)
        facts['issue_health'] = health
        facts['top_issues'] = top
        return facts
```

- [ ] **Step 5: 真实项目验证（spec §7 验证项 1）**

```bash
PYTHONPATH=. GITHUB_TOKEN=$(grep GITHUB_TOKEN .env | cut -d= -f2 | tr -d '"') python3 - <<'EOF'
from framework.core.config_loader import ConfigLoader
from framework.core.db import Database
from framework.stages.discover import DiscoverStage
s = DiscoverStage(ConfigLoader(), Database())

# 有 tests/CI 的成熟项目
f1 = s._fetch_structure_facts('psf/requests')
assert f1 and f1['has_tests'] and f1['has_ci'], f1
assert f1['issue_health'] is not None and f1['issue_health']['issue_count'] > 0, f1['issue_health']
assert all('pull_request' not in t for t in f1['top_issues'])
print('requests:', {k: f1[k] for k in ('has_tests','has_ci','has_docs','core_paths','partial')})

# 依赖高层编排框架的项目（应命中 known_ecosystem_packages）
f2 = s._fetch_structure_facts('langchain-ai/langchain')
assert f2, 'langchain fetch failed'
assert len(f2['matched_ecosystem_packages']) > 0, f2['matched_ecosystem_packages']
print('langchain matched:', f2['matched_ecosystem_packages'][:5])

# 从零实现的项目（不应命中）
f3 = s._fetch_structure_facts('octocat/Hello-World')
assert f3 is not None
assert f3['matched_ecosystem_packages'] == [], f3['matched_ecosystem_packages']
print('hello-world core_paths:', f3['core_paths'], f3['core_paths_reason'])
print('L1 fetcher OK')
EOF
```

Expected: 输出 `L1 fetcher OK`（langchain 单测若 matched 为空属名单语义问题，需检查 dependencies 解析；octocat 无清单文件 → deps/matched 为空属预期）

- [ ] **Step 6: Commit**

```bash
git add framework/stages/discover.py
git commit -m "feat: L1 structural facts fetcher (tree, manifest deps, issue health)"
```

