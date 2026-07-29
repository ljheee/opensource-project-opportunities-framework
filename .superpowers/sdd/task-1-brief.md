### Task 1: 配置与 schema 基础

**Files:**
- Modify: `config.yaml`
- Modify: `framework/core/config_loader.py`（`get_backfill_config` 后）
- Modify: `framework/core/db.py`（`_migrate_projects`、`_migrate_analyses`、`_create_analyses`）

**Interfaces:**
- Produces:
  - `ConfigLoader.get_structure_max_per_day() -> int`（默认 50）
  - `projects.structure_json` / `analyses.evidence_json` 两列（后续任务直接读写）
  - config 键：`sources.github.structure_max_per_day`、`filters.known_ecosystem_packages`、权重 0.40/0.30/0.20/0.10

- [ ] **Step 1: 写失败验证**

```bash
PYTHONPATH=. python3 -c "
from framework.core.config_loader import ConfigLoader
from framework.core.db import Database
c = ConfigLoader()
assert c.get_structure_max_per_day() == 50, 'getter missing'
db = Database('/tmp/t1_test.db'); db.init_tables()
conn = db.get_conn()
pcols = [r[1] for r in conn.execute('PRAGMA table_info(projects)').fetchall()]
acols = [r[1] for r in conn.execute('PRAGMA table_info(analyses)').fetchall()]
assert 'structure_json' in pcols, pcols
assert 'evidence_json' in acols, acols
conn.close()
print('OK')
"
```

Expected: FAIL — `AttributeError: 'ConfigLoader' object has no attribute 'get_structure_max_per_day'`

- [ ] **Step 2: 修改 config.yaml**

`sources.github` 段（`backfill_max_per_day` 后）追加：

```yaml
    structure_max_per_day: 50
```

`filters` 段（`tech_layer_rules` 后）追加：

```yaml
  known_ecosystem_packages:
    - "langchain"
    - "langchain-core"
    - "llama-index"
    - "openai"
    - "anthropic"
    - "llama-cpp-python"
    - "haystack-ai"
    - "semantic-kernel"
    - "dspy"
```

（语义：仅高层编排框架/SDK，明确不含 torch/transformers/numpy 等基础库）

`early_burst.metrics` 权重改为：

```yaml
    star_velocity:
      weight: 0.40
    activity_index:
      weight: 0.30
    community_buzz:
      weight: 0.10
      thresholds:
        default_score: 0.3
        reaction_total_full: 50
        active_issues_full: 5
        avg_comments_full: 5
    novelty_signal:
      weight: 0.20
```

（community_buzz.thresholds 保留原 default_score，新增三个实值阈值）

- [ ] **Step 3: config_loader.py 追加 getter**

在 `get_backfill_config` 方法之后插入：

```python
    def get_structure_max_per_day(self) -> int:
        raw = ((self.load().get('sources') or {}).get('github') or {}).get('structure_max_per_day', 50)
        try:
            val = int(raw)
        except (ValueError, TypeError):
            return 50
        return val if val > 0 else 50
```

- [ ] **Step 4: db.py 三处加列**

(a) `_migrate_projects` 末尾追加：

```python
        self._add_column_if_missing(conn, 'projects', 'structure_json', 'TEXT')
```

(b) `_migrate_analyses` 的 ALTER 段（`self._add_column_if_missing(conn, 'analyses', 'analyzer_version', 'TEXT')` 后）追加：

```python
        self._add_column_if_missing(conn, 'analyses', 'evidence_json', 'TEXT')
```

(c) `_migrate_analyses` 的 CHECK 重建分支：`analyses_new` 的 CREATE TABLE 列清单在 `analyzer_version TEXT` 后加 `,\n                evidence_json TEXT`；INSERT INTO analyses_new 的列清单和 SELECT 列清单同步各加 `evidence_json`。

(d) `_create_analyses` 的 CREATE TABLE 同样在 `analyzer_version TEXT` 后加 `,\n                evidence_json TEXT`。

- [ ] **Step 5: 重跑 Step 1 验证 + 生产库软迁移**

```bash
python3 framework/stages/init_db.py && sqlite3 data/framework.db "PRAGMA table_info(projects);" | grep structure_json && sqlite3 data/framework.db "PRAGMA table_info(analyses);" | grep evidence_json && echo "prod migration OK"
```

Expected: Step 1 输出 `OK`；生产库两列存在且数据未受影响

- [ ] **Step 6: Commit**

```bash
git add config.yaml framework/core/config_loader.py framework/core/db.py
git commit -m "feat: config keys and soft-migrated columns for tiered deep analysis"
```

