### Task 2: `_github_request` 可选 headers + topics 查询转向新项目

**Files:**
- Modify: `framework/stages/discover.py:62-137`（`_github_request`）
- Modify: `framework/stages/discover.py:440-487`（`discover_topics`）

**Interfaces:**
- Consumes: `ConfigLoader.get_created_within_days()`（Task 1）
- Produces: `_github_request(url, params=None, is_search=False, headers=None) -> Dict` — Task 3/5 的 stargazers/commits 请求依赖 headers 参数

- [ ] **Step 1: `_github_request` 签名加 headers 参数**

`framework/stages/discover.py:62-63` 的签名改为：

```python
    def _github_request(self, url: str, params: Optional[Dict] = None,
                       is_search: bool = False, headers: Optional[Dict] = None) -> Dict:
        """Make GitHub API request with rate limit handling.

        headers: optional override/merge into the default HEADERS
        (e.g. stargazers endpoints need Accept: application/vnd.github.star+json).
        """
```

方法内第 91-96 行的 `requests.get(...)` 调用前，构造实际使用的 header（原 `headers=HEADERS` 替换）：

```python
                req_headers = {**HEADERS, **headers} if headers else HEADERS
                response = requests.get(
                    url,
                    headers=req_headers,
                    params=params,
                    timeout=30
                )
```

- [ ] **Step 2: `__init__` 读取 created cutoff**

`DiscoverStage.__init__`（discover.py:55-60）末尾追加：

```python
        self.created_within_days = config.get_created_within_days()
```

- [ ] **Step 3: `discover_topics` 查询改造**

discover.py:456 的 query 构造与 460 行的请求改为：

```python
                cutoff = (datetime.now(timezone.utc) - timedelta(days=self.created_within_days)).strftime('%Y-%m-%d')
                query = f"topic:{safe_topic} language:{safe_lang} stars:{self.star_min}..{self.star_max} created:>{cutoff}"
                url = "https://api.github.com/search/repositories"

                try:
                    data = self._github_request(url, {"q": query, "sort": "updated", "per_page": 30}, is_search=True)
```

- [ ] **Step 4: dry-run 验证（spec §4 验证项 1）**

```bash
GITHUB_TOKEN=$(grep GITHUB_TOKEN .env | cut -d= -f2) python3 framework/stages/discover.py --dry-run 2>&1 | head -30
```

Expected: 正常列出项目无报错。再验证 cutoff 生效：

```bash
PYTHONPATH=. python3 -c "
from framework.core.config_loader import ConfigLoader
from framework.core.db import Database
from framework.stages.discover import DiscoverStage
from datetime import datetime, timezone, timedelta
s = DiscoverStage(ConfigLoader(), Database())
cutoff = (datetime.now(timezone.utc) - timedelta(days=s.created_within_days)).strftime('%Y-%m-%d')
print('cutoff =', cutoff)
assert s.created_within_days == 730
"
```

Expected: 打印 `cutoff = 2024-07-28` 左右 + 断言通过

- [ ] **Step 5: Commit**

```bash
git add framework/stages/discover.py
git commit -m "feat: topics search targets recent repos (created cutoff + sort=updated)"
```

