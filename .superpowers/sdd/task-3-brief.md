### Task 3: Stargazers 时间戳回溯核心函数

**Files:**
- Modify: `framework/stages/discover.py`（`DiscoverStage` 新增两个方法）

**Interfaces:**
- Consumes: `_github_request(..., headers=...)`（Task 2）、`ConfigLoader.get_backfill_config()`（Task 1）、`Database.get_conn()`
- Produces: `_backfill_star_history(project_id: str, stars: int, conn) -> int` — 返回写入的合成行数；Task 4 在入库/存量流程中调用它

- [ ] **Step 1: 写失败验证（临时脚本）**

```bash
cat > /tmp/verify_backfill.py <<'EOF'
import sys
sys.path.insert(0, '.')
from framework.core.config_loader import ConfigLoader
from framework.core.db import Database
from framework.stages.discover import DiscoverStage

s = DiscoverStage(ConfigLoader(), Database())
assert hasattr(s, '_backfill_star_history'), 'method missing'
print('OK')
EOF
PYTHONPATH=. python3 /tmp/verify_backfill.py
```

Expected: FAIL — `AssertionError: method missing`

- [ ] **Step 2: 实现回溯方法**

在 `_sample_star_count` 方法（discover.py:309-311）之后插入：

```python
    def _fetch_stargazer_timestamps(self, full_name: str, stars: int) -> List[str]:
        """Fetch starred_at timestamps, newest first, bounded by backfill config."""
        cfg = self.config.get_backfill_config()
        max_pages = cfg['max_pages']
        if stars <= 0:
            return []
        # GitHub stargazers endpoint only serves the first 400 pages (page>400 -> 422)
        last_page = min((stars + 99) // 100, 400)
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=35)).date()
        timestamps: List[str] = []
        pages_fetched = 0
        for page in range(last_page, 0, -1):
            if pages_fetched >= max_pages:
                break
            try:
                data = self._github_request(
                    f"https://api.github.com/repos/{quote(full_name, safe='')}/stargazers",
                    params={"per_page": 100, "page": page},
                    headers={'Accept': 'application/vnd.github.star+json'},
                )
            except GitHubAPIError as e:
                print(f"  Backfill page {page} failed for {full_name}: {e}")
                break
            pages_fetched += 1
            if not isinstance(data, list):
                break
            page_earliest = None
            for item in data:
                if not isinstance(item, dict):
                    continue
                ts = item.get('starred_at')
                if not ts:
                    continue
                timestamps.append(ts)
                try:
                    d = datetime.fromisoformat(ts.replace('Z', '+00:00')).date()
                except (ValueError, TypeError):
                    continue
                if page_earliest is None or d < page_earliest:
                    page_earliest = d
            # Stop when the whole page is older than the 35-day window
            if page_earliest is not None and page_earliest < cutoff_date:
                break
        return timestamps

    def _backfill_star_history(self, project_id: str, stars: int, conn=None) -> int:
        """Rebuild daily star history from stargazer timestamps (first-seen projects).

        Returns number of synthetic rows written. Skips entirely if the project
        already has star_history rows. Synthetic rows use 'YYYY-MM-DD' dates to
        match db.sample_star_count's date(?) format and UNIQUE(project_id, sampled_at).
        """
        should_close = conn is None
        conn = conn or self.db.get_conn()
        try:
            existing = conn.execute(
                'SELECT 1 FROM star_history WHERE project_id = ? LIMIT 1', (project_id,)
            ).fetchone()
            if existing:
                return 0
            timestamps = self._fetch_stargazer_timestamps(project_id, stars)
            if not timestamps:
                return 0
            # Count stars per UTC date; accumulate oldest -> newest
            per_day: Dict[str, int] = {}
            for ts in timestamps:
                day = ts[:10]
                per_day[day] = per_day.get(day, 0) + 1
            # Total stars covered by fetched timestamps; stars before the oldest
            # fetched timestamp form the baseline so curves end at current count.
            covered = len(timestamps)
            baseline = max(stars - covered, 0)
            written = 0
            cumulative = baseline
            for day in sorted(per_day):
                cumulative += per_day[day]
                conn.execute(
                    'INSERT OR IGNORE INTO star_history (project_id, sampled_at, stars) VALUES (?, ?, ?)',
                    (project_id, day, cumulative)
                )
                written += 1
            if should_close:
                conn.commit()
            print(f"  Backfilled {written} days of star history for {project_id}")
            return written
        finally:
            if should_close:
                conn.close()
```

- [ ] **Step 3: 重跑 Step 1 验证**

Expected: 输出 `OK`

- [ ] **Step 4: 真实项目端到端核对（spec §4 验证项 2）**

挑一个近期爆发的小型项目（如当日 trending 第一名，<3000 stars）：

```bash
cat > /tmp/verify_backfill_e2e.py <<'EOF'
import sys
sys.path.insert(0, '.')
from framework.core.config_loader import ConfigLoader
from framework.core.db import Database
from framework.stages.discover import DiscoverStage

REPO = sys.argv[1]  # e.g. "owner/repo"
db = Database(':memory:') if False else Database('/tmp/backfill_test.db')
db.init_tables()
s = DiscoverStage(ConfigLoader(), db)
conn = db.get_conn()
stars = s._github_request(f'https://api.github.com/repos/{REPO}').get('stargazers_count', 0)
n = s._backfill_star_history(REPO, stars, conn=conn)
rows = conn.execute(
    'SELECT sampled_at, stars FROM star_history WHERE project_id=? ORDER BY sampled_at', (REPO,)
).fetchall()
for r in rows:
    print(dict(r))
assert n == len(rows) > 0, 'no rows written'
# 幂等：第二次调用必须写 0 行
assert s._backfill_star_history(REPO, stars, conn=conn) == 0, 'not idempotent'
# 单调性：合成历史必须单调不减
vals = [r['stars'] for r in rows]
assert vals == sorted(vals), 'not monotonic'
print('E2E OK:', n, 'days, latest =', vals[-1], '/ actual', stars)
EOF
PYTHONPATH=. GITHUB_TOKEN=$(grep GITHUB_TOKEN .env | cut -d= -f2 | tr -d '"') python3 /tmp/verify_backfill_e2e.py owner/repo
```

Expected: 打印逐日曲线，`E2E OK`；最后一行 stars ≈ 实际值（允许小误差：回溯期间 star 变动 + unstar 单向低估，见 spec §2.2 已知偏差）。手动与 GitHub 页面 star 曲线形状比对。

- [ ] **Step 5: Commit**

```bash
git add framework/stages/discover.py
git commit -m "feat: backfill star history from stargazer timestamps on first-seen projects"
```

