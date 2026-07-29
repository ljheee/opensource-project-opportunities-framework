### Task 5: Contributors 实采（commits API）

**Files:**
- Modify: `framework/stages/discover.py:396-401`（`_calculate_and_store_burst_score` 的 novelty 调用点）
- Modify: `framework/stages/discover.py`（新增 `_fetch_weekly_contributors`）

**Interfaces:**
- Consumes: `_github_request(...)`（Task 2）
- Produces: `_fetch_weekly_contributors(project_id: str) -> Optional[int]`；评分时 novelty 的 `unique_contributors_weekly` 实参；`projects.contributor_count` 仅在 NULL 时回填

- [ ] **Step 1: 实现采集方法**

在 `_backfill_within_budget` 之后插入：

```python
    def _fetch_weekly_contributors(self, full_name: str) -> Optional[int]:
        """Count distinct commit authors in the last 7 days. None on failure."""
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        try:
            commits = self._github_request(
                f"https://api.github.com/repos/{quote(full_name, safe='/')}/commits",
                params={"since": since, "per_page": 100},
            )
        except GitHubAPIError as e:
            print(f"  Contributors fetch failed for {full_name}: {e}")
            return None
        if not isinstance(commits, list):
            return None
        authors = set()
        for c in commits:
            if not isinstance(c, dict):
                continue
            login = ((c.get('author') or {}) or {}).get('login')
            if login:
                authors.add(login.lower())
                continue
            email = (((c.get('commit') or {}).get('author') or {}) or {}).get('email')
            if email:
                authors.add(str(email).lower())
        return len(authors)
```

- [ ] **Step 2: 评分集成**

`_calculate_and_store_burst_score` 中（discover.py:399-401），把：

```python
            novelty_score = self.scoring.calculate_novelty(
                proj['first_commit_at'] or proj['created_at'], 1
            )
```

改为（仅当 contributor_count 为 NULL 时采集，随后直接用它）：

```python
            contributor_count = proj['contributor_count']
            if contributor_count is None:
                fetched = self._fetch_weekly_contributors(project_id)
                if fetched is not None:
                    contributor_count = fetched
                    conn.execute(
                        'UPDATE projects SET contributor_count = ? WHERE id = ?',
                        (fetched, project_id)
                    )
            novelty_score = self.scoring.calculate_novelty(
                proj['first_commit_at'] or proj['created_at'],
                contributor_count if contributor_count is not None else 1
            )
```

- [ ] **Step 3: 验证**

```bash
PYTHONPATH=. GITHUB_TOKEN=$(grep GITHUB_TOKEN .env | cut -d= -f2 | tr -d '"') python3 -c "
from framework.core.config_loader import ConfigLoader
from framework.core.db import Database
from framework.stages.discover import DiscoverStage
s = DiscoverStage(ConfigLoader(), Database())
n = s._fetch_weekly_contributors('octocat/Hello-World')
print('octocat/Hello-World weekly contributors:', n)
assert n is not None
"
```

Expected: 打印一个整数（可能为 0——该项目多年无 commit，0 也是正确的实采结果），断言通过

- [ ] **Step 4: Commit**

```bash
git add framework/stages/discover.py
git commit -m "feat: sample real weekly contributors for novelty signal"
```

