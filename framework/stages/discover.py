#!/usr/bin/env python3
"""
Stage 1: Discover AI projects from multiple sources.
Samples star counts to build velocity history.
"""
import os
import sys
import json
import time
import argparse
import re
import requests
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Set, Tuple
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from framework.core.config_loader import ConfigLoader
from framework.core.db import Database
from framework.core.scoring_engine import ScoringEngine


# GitHub API Configuration
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN', '')
HEADERS = {
    'Accept': 'application/vnd.github+json',
    'X-GitHub-Api-Version': '2022-11-28'
}
if GITHUB_TOKEN:
    HEADERS['Authorization'] = f'Bearer {GITHUB_TOKEN}'

# Rate limiting state
_last_request_time = 0


class GitHubAPIError(Exception):
    """GitHub API error with retry info."""
    def __init__(self, message: str, status_code: int = None, retry_after: int = None):
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after


def _to_bool(val) -> bool:
    """Coerce config value to bool (handles string 'false', '0', etc.)."""
    if isinstance(val, str):
        return val.lower() not in ('false', '0', 'no', 'off', '')
    return bool(val)


class DiscoverStage:
    """Multi-source project discovery stage."""

    def __init__(self, config: ConfigLoader, db: Database):
        self.config = config
        self.db = db
        self.scoring = ScoringEngine(config.get_early_burst_config())
        self.resilience = config.get_resilience_config()
        self.star_min, self.star_max = config.get_star_range()
        self.created_within_days = config.get_created_within_days()
        self._structures_done = 0
        self._event_rates_done = 0
        self._contributors_done = 0

    def _github_request(self, url: str, params: Optional[Dict] = None,
                       is_search: bool = False, headers: Optional[Dict] = None) -> Dict:
        """Make GitHub API request with rate limit handling.

        headers: optional override/merge into the default HEADERS
        (e.g. stargazers endpoints need Accept: application/vnd.github.star+json).
        """
        global _last_request_time

        # Rate limiting for search API
        if is_search:
            elapsed = time.time() - _last_request_time
            if elapsed < 2:
                time.sleep(max(0, 2 - elapsed))
        else:
            elapsed = time.time() - _last_request_time
            if elapsed < 0.5:
                time.sleep(max(0, 0.5 - elapsed))

        github_api_cfg = self.resilience.get('github_api') or {}
        try:
            max_retries = int(github_api_cfg.get('max_retries', 3))
        except (ValueError, TypeError):
            max_retries = 3
        try:
            retry_delay = max(int(github_api_cfg.get('retry_delay_seconds', 60)), 0)
        except (ValueError, TypeError):
            retry_delay = 60
        if max_retries < 1:
            max_retries = 1

        for attempt in range(max_retries):
            try:
                req_headers = {**HEADERS, **headers} if headers else HEADERS
                response = requests.get(
                    url,
                    headers=req_headers,
                    params=params,
                    timeout=30
                )
                _last_request_time = time.time()

                # Handle rate limiting
                if response.status_code == 403 and 'rate limit' in response.text.lower():
                    if attempt >= max_retries - 1:
                        raise GitHubAPIError(f"Rate limited after {attempt + 1} attempts")
                    try:
                        reset_time = int(response.headers.get('X-RateLimit-Reset') or 0)
                    except (ValueError, TypeError):
                        reset_time = 0
                    wait_time = max(reset_time - int(time.time()), 60)
                    print(f"  Rate limited. Waiting {wait_time}s...")
                    time.sleep(min(wait_time, 3600))
                    continue

                if response.status_code == 429:
                    if attempt >= max_retries - 1:
                        raise GitHubAPIError(f"Too many requests after {attempt + 1} attempts")
                    try:
                        retry_after = max(int(response.headers.get('Retry-After') or 60), 0)
                    except (ValueError, TypeError):
                        retry_after = 60
                    print(f"  Too many requests. Waiting {retry_after}s...")
                    time.sleep(min(retry_after, retry_delay))
                    continue

                if response.status_code == 404:
                    raise GitHubAPIError(f"Not found: {url}", status_code=404)

                response.raise_for_status()
                try:
                    return response.json()
                except ValueError as e:
                    raise GitHubAPIError(f"Invalid JSON response: {e}")

            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    wait = retry_delay * (attempt + 1)
                    print(f"  Request failed (attempt {attempt + 1}). Waiting {wait}s...")
                    time.sleep(wait)
                else:
                    raise GitHubAPIError(f"Failed after {attempt + 1} attempts: {e}")

        raise GitHubAPIError("Unexpected end of retry loop")

    def _should_skip_repo(self, repo: Dict) -> Tuple[bool, str]:
        """Check if repository should be skipped based on filters."""
        filters = self.config.get_filters()

        try:
            stars = int(repo.get('stargazers_count') or 0)
        except (ValueError, TypeError):
            stars = 0
        if stars < self.star_min:
            return True, f"stars_too_few:{stars}"
        if stars > self.star_max:
            return True, f"stars_too_many:{stars}"

        if repo.get('archived'):
            return True, "archived"

        # Check stale (no commits in 180 days)
        pushed = repo.get('pushed_at') or ''
        if pushed:
            try:
                pushed_dt = datetime.fromisoformat(pushed.replace('Z', '+00:00'))
                if pushed_dt.tzinfo is None:
                    pushed_dt = pushed_dt.replace(tzinfo=timezone.utc)
                stale_cutoff = datetime.now(timezone.utc) - timedelta(days=180)
                if pushed_dt < stale_cutoff:
                    return True, f"stale_since:{pushed[:10]}"
            except (ValueError, TypeError):
                pass

        # Check skip patterns (whole-word match to avoid false positives)
        name = (repo.get('name') or '').lower()
        desc = (repo.get('description') or '').lower()
        text = f"{name} {desc}"
        skip_patterns = filters.get('skip_patterns', [])
        if not isinstance(skip_patterns, list):
            skip_patterns = []
        for pattern in skip_patterns:
            pattern = str(pattern) if pattern is not None else ''
            if not pattern:
                continue
            pat_lower = pattern.lower()
            for match in re.finditer(re.escape(pat_lower), text):
                start, end = match.span()
                left_ok = start == 0 or not text[start - 1].isalnum()
                right_ok = end == len(text) or not text[end].isalnum()
                if left_ok and right_ok:
                    return True, f"skip_pattern:{pattern}"

        if repo.get('fork'):
            return True, "is_fork"

        # Check required filters from config
        required = filters.get('required', {})
        try:
            size = int(repo.get('size') or 0)
        except (ValueError, TypeError):
            size = 0
        if _to_bool(required.get('has_code')) and size == 0:
            return True, "empty_repo"

        # Proxy for has_readme: GitHub usually populates description from README
        if _to_bool(required.get('has_readme')) and not repo.get('description'):
            return True, "no_readme"

        return False, ""

    def _upsert_project(self, repo: Dict, source: str, signal: str, conn=None):
        """Insert or update project in database.

        Uses the provided connection if available; otherwise opens its own,
        commits, and closes.
        """
        should_close = conn is None
        conn = conn or self.db.get_conn()
        try:
            now = datetime.now(timezone.utc).isoformat()
            project_id = repo.get('full_name')
            if not project_id:
                raise ValueError("Repository missing full_name")

            # Check if project exists and get current metadata for change detection
            existing = conn.execute(
                'SELECT topics, description, status, filter_reason FROM projects WHERE id = ?', (project_id,)
            ).fetchone()

            new_topics = json.dumps(repo.get('topics') or [])
            new_desc = (repo.get('description') or '')[:500]

            if existing:
                old_topics = existing['topics'] or '[]'
                old_desc = existing['description'] or ''
                old_status = existing['status']
                old_filter_reason = existing['filter_reason']
                if old_status in ('active', 'scheduled', 'analyzing'):
                    reset_status = old_status
                    reset_filter_reason = old_filter_reason
                elif old_status == 'filtered_skip':
                    # Project has passed current discovery filters;
                    # always reset so semantic filtering can re-evaluate
                    reset_status = 'discovered'
                    reset_filter_reason = None
                else:
                    reset_status = 'discovered'
                    reset_filter_reason = None
            else:
                reset_status = 'discovered'
                reset_filter_reason = None

            category = self.config.get_category().name

            # Insert or update project
            conn.execute('''
                INSERT INTO projects (
                    id, name, url, language, stars, open_issues, forks,
                    created_at, first_commit_at, last_commit_at, topics, description,
                    category, source, status, filter_reason, first_seen_at, last_fetched_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    url = excluded.url,
                    language = excluded.language,
                    prev_stars = projects.stars,
                    stars = excluded.stars,
                    prev_open_issues = projects.open_issues,
                    open_issues = excluded.open_issues,
                    forks = excluded.forks,
                    created_at = COALESCE(projects.created_at, excluded.created_at),
                    first_commit_at = COALESCE(projects.first_commit_at, excluded.first_commit_at),
                    last_commit_at = excluded.last_commit_at,
                    topics = excluded.topics,
                    description = excluded.description,
                    category = excluded.category,
                    source = excluded.source,
                    filter_reason = excluded.filter_reason,
                    last_fetched_at = excluded.last_fetched_at,
                    first_seen_at = COALESCE(NULLIF(projects.first_seen_at, ''), excluded.first_seen_at),
                    status = CASE
                        WHEN projects.status IN ('active', 'scheduled', 'analyzing')
                            THEN projects.status
                        ELSE excluded.status
                    END
            ''', (
                project_id,
                repo.get('name'),
                repo.get('html_url'),
                repo.get('language'),
                repo.get('stargazers_count') or 0,
                repo.get('open_issues_count') or 0,
                repo.get('forks_count') or 0,
                repo.get('created_at'),
                repo.get('created_at'),
                repo.get('pushed_at'),
                new_topics,
                new_desc,
                category,
                source,
                reset_status,
                reset_filter_reason,
                now,
                now
            ))

            if should_close:
                conn.commit()

            return project_id
        finally:
            if should_close:
                conn.close()

    def _sample_star_count(self, project_id: str, stars: int, conn=None):
        """Sample current star count for velocity tracking."""
        self.db.sample_star_count(project_id, stars, conn=conn)

    def _fetch_recent_star_rate(self, full_name: str) -> Optional[Dict]:
        """Estimate recent star gain rate from the repo events feed (WatchEvents).

        Replacement for stargazers-timestamp backfill (that endpoint is
        GitHub-restricted: REST 404 / GraphQL edges stripped, confirmed 2026-07-29
        in both local and Actions networks). Events retention in practice covers
        only the most recent ~0.5-6 days, so this yields a *recent* rate, not a
        full history. WatchEvents are gross star adds (unstars generate no event),
        so the rate slightly overestimates net velocity — documented bias.
        """
        max_pages = 3
        # 7-day window matching the 7-day velocity extrapolation below — a wider
        # counting window would smear old bursts into "bursting now" (review H1).
        window_days = 7
        window_seconds = window_days * 86400
        now = datetime.now(timezone.utc)
        stars_gained = 0
        oldest_seen = None
        for page in range(1, max_pages + 1):
            try:
                events = self._github_request(
                    f"https://api.github.com/repos/{quote(full_name, safe='/')}/events",
                    params={"per_page": 100, "page": page},
                )
            except GitHubAPIError as e:
                print(f"  Events fetch failed for {full_name}: {e}")
                return None
            if not isinstance(events, list) or not events:
                break
            page_oldest = None
            for e in events:
                if not isinstance(e, dict):
                    continue
                ts = e.get('created_at')
                if not ts:
                    continue
                try:
                    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                except (ValueError, TypeError):
                    continue
                if page_oldest is None or dt < page_oldest:
                    page_oldest = dt
                if (e.get('type') == 'WatchEvent'
                        and 0 <= (now - dt).total_seconds() <= window_seconds):
                    stars_gained += 1
            if page_oldest is not None and (oldest_seen is None or page_oldest < oldest_seen):
                oldest_seen = page_oldest
            if page_oldest is not None and (now - page_oldest).days >= window_days:
                break
            if len(events) < 100:
                break
        if oldest_seen is None:
            return None
        days_covered = min((now - oldest_seen).total_seconds() / 86400, float(window_days))
        # Floor the divisor at 1 day: sub-day windows (dense feeds on hot repos
        # exhaust quickly) would otherwise explode the rate; flooring merely
        # compresses it — a 126-stars-in-12h burst still scores as a burst.
        rate_days = max(days_covered, 1.0)
        return {'stars_gained': stars_gained,
                'days_covered': round(days_covered, 2),
                'rate': round(stars_gained / rate_days, 2)}

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
        # Manifest paths: root manifest first by ecosystem-agnostic priority;
        # monorepo fallback merges up to 10 nested manifests of the
        # highest-priority type present (sorted for determinism).
        manifest_paths: List[str] = []
        for name in ('pyproject.toml', 'requirements.txt', 'package.json', 'Cargo.toml', 'go.mod'):
            if name in all_paths:
                manifest_paths = [name]
                break
        if not manifest_paths:
            for name in ('pyproject.toml', 'requirements.txt', 'package.json', 'Cargo.toml', 'go.mod'):
                nested = sorted(p for p in all_paths if '/' in p and p.rsplit('/', 1)[-1] == name)
                if nested:
                    manifest_paths = nested[:10]
                    break
        facts['_manifest_paths'] = manifest_paths
        return facts

    def _fetch_manifest_deps(self, full_name: str, manifest_paths: List[str]) -> Tuple[List[str], List[str]]:
        """Fetch dependency manifests via raw (no API quota). Returns (deps, matched).
        Accepts multiple paths (monorepo); deps are merged in order, deduped.
        """
        if not manifest_paths:
            return [], []
        deps: List[str] = []
        seen = set()

        def _add(name: str):
            if name and name not in seen:
                seen.add(name)
                deps.append(name)

        for manifest_path in manifest_paths:
            try:
                r = requests.get(
                    f"https://raw.githubusercontent.com/{full_name}/HEAD/{manifest_path}",
                    headers={'User-Agent': 'Mozilla/5.0'}, timeout=15
                )
                if r.status_code != 200:
                    continue
                text = r.text[:200 * 1024]
            except requests.exceptions.RequestException:
                continue
            base = manifest_path.rsplit('/', 1)[-1]
            if base == 'package.json':
                try:
                    pkg = json.loads(text)
                    for d in sorted(set(list((pkg.get('dependencies') or {}).keys())
                                    + list((pkg.get('devDependencies') or {}).keys()))):
                        _add(d)
                except (json.JSONDecodeError, TypeError):
                    pass
            elif base in ('Cargo.toml', 'pyproject.toml'):
                def _array_names(ls):
                    # PEP 621 数组元素带版本约束（"langchain-core>=1.4.7,<2.0.0"），
                    # 需先取引号内容再截断版本/环境标记部分
                    out = []
                    for raw in re.findall(r'"([^"]+)"', ls):
                        n = re.split(r'[\s=><~^;\[!(]', raw, maxsplit=1)[0].strip().strip('\\')
                        if n and re.match(r'^(?=.*[A-Za-z])[A-Za-z0-9_.-]+$', n):
                            out.append(n)
                    return out

                in_deps = False     # poetry/cargo-style [..dependencies] section
                in_project = False  # PEP 621 [project] section
                array_continues = False
                for line in text.splitlines():
                    ls = line.strip()
                    if ls.startswith('[') and ls.endswith(']') and '=' not in ls:
                        # 段头：[dependencies] / [project] / [tool.poetry.dependencies] 等
                        in_deps = 'dependencies' in ls and 'optional-dependencies' not in ls and 'dev-dependencies' not in ls
                        in_project = ls == '[project]'
                        array_continues = False
                        continue
                    if in_deps or in_project:
                        # PEP 621: [project] 段内 dependencies = ["a", "b"] 可能跨行
                        if ls.startswith('dependencies') and '=' in ls:
                            array_continues = '[' in ls and ']' not in ls
                            for n in _array_names(ls):
                                _add(n)
                            continue
                        if array_continues:
                            for n in _array_names(ls):
                                _add(n)
                            if ']' in ls:
                                array_continues = False
                            continue
                        if in_deps and ls and not ls.startswith('#') and '=' in ls:
                            name = re.split(r'[\s=\[("\'><~^]', ls, maxsplit=1)[0].strip().strip('"\'')
                            if name and re.match(r'^[A-Za-z0-9_.-]+$', name) and name != 'dependencies':
                                _add(name)
            elif base == 'go.mod':
                for line in text.splitlines():
                    ls = line.strip()
                    if not ls or ls.startswith('//'):
                        continue
                    first = ls.split()[0] if ls.split() else ''
                    if first in ('module', 'go', 'require', 'replace', 'exclude', ')', '('):
                        continue
                    name = first.strip()
                    if name and re.match(r'^[A-Za-z0-9_./-]+$', name):
                        _add(name)
            else:  # requirements.txt
                for line in text.splitlines():
                    ls = line.strip()
                    if not ls or ls.startswith(('#', '-')):
                        continue
                    name = re.split(r'[\s=><~^(;]', ls, maxsplit=1)[0].strip()
                    if name and re.match(r'^[A-Za-z0-9_.-]+$', name):
                        _add(name)
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
        deps, matched = self._fetch_manifest_deps(full_name, facts.pop('_manifest_paths'))
        facts['dependencies'] = deps
        facts['matched_ecosystem_packages'] = matched
        health, top = self._fetch_issue_health(full_name)
        facts['issue_health'] = health
        facts['top_issues'] = top
        return facts

    def _structure_within_budget(self, project_id: str, conn) -> Optional[Dict]:
        """Fetch L1 structure facts for one project if due and within budget.

        Returns the facts dict if freshly fetched this call, else None.
        Freshness: structure_json missing / fetched_at NULL / fetched_at older
        than 10 days. Failure gating: 3 consecutive failures -> skip for 30 days.
        """
        row = conn.execute(
            'SELECT structure_json FROM projects WHERE id = ?', (project_id,)
        ).fetchone()
        existing = None
        if row and row['structure_json']:
            try:
                existing = json.loads(row['structure_json'])
            except (json.JSONDecodeError, TypeError):
                existing = None
        now = datetime.now(timezone.utc)
        if existing and existing.get('fetched_at'):
            try:
                fetched = datetime.fromisoformat(str(existing['fetched_at']).replace('Z', '+00:00'))
                if fetched.tzinfo is None:
                    fetched = fetched.replace(tzinfo=timezone.utc)
                if (now - fetched).days < 10:
                    return None  # fresh enough
            except (ValueError, TypeError):
                pass
        # Failure gating: 3 consecutive failures -> 30-day cooldown
        if existing and not existing.get('fetched_at'):
            try:
                fail_count = int(existing.get('fail_count') or 0)
            except (ValueError, TypeError):
                fail_count = 0
            last_fail = existing.get('last_fail_at')
            if fail_count >= 3 and last_fail:
                try:
                    lf = datetime.fromisoformat(str(last_fail).replace('Z', '+00:00'))
                    if lf.tzinfo is None:
                        lf = lf.replace(tzinfo=timezone.utc)
                    if (now - lf).days < 30:
                        return None
                except (ValueError, TypeError):
                    pass
        budget = self.config.get_structure_max_per_day()
        if self._structures_done >= budget:
            return None
        facts = self._fetch_structure_facts(project_id)
        self._structures_done += 1
        if facts is None:
            prev_fail = 0
            if existing:
                try:
                    prev_fail = int(existing.get('fail_count') or 0)
                except (ValueError, TypeError):
                    prev_fail = 0
            # 保留旧的成功事实（若存在），只更新失败计数——刷新失败
            # 不应销毁仍可用的旧数据（review 修正）
            failure_record = dict(existing) if existing else {}
            failure_record['fetched_at'] = (existing or {}).get('fetched_at')
            failure_record['fail_count'] = prev_fail + 1
            failure_record['last_fail_at'] = now.isoformat()
            conn.execute(
                'UPDATE projects SET structure_json = ? WHERE id = ?',
                (json.dumps(failure_record, ensure_ascii=False), project_id)
            )
            return None
        facts['fetched_at'] = now.isoformat()
        facts['fail_count'] = 0
        conn.execute(
            'UPDATE projects SET structure_json = ? WHERE id = ?',
            (json.dumps(facts, ensure_ascii=False), project_id)
        )
        return facts

    def _calculate_and_store_burst_score(self, project_id: str, conn=None):
        """Calculate early-burst score from sampled data."""
        should_close = conn is None
        conn = conn or self.db.get_conn()
        try:
            # Get current project info
            proj = conn.execute(
                'SELECT * FROM projects WHERE id = ?', (project_id,)
            ).fetchone()

            if not proj:
                return

            try:
                current_stars = int(proj['stars']) if proj['stars'] is not None else 0
            except (ValueError, TypeError):
                current_stars = 0

            # Get star history from shared conn if available, else new conn
            if should_close:
                history = self.db.get_project_star_history(project_id, days=35)
            else:
                cursor = conn.execute('''
                    SELECT * FROM star_history
                    WHERE project_id = ?
                    AND sampled_at >= date('now', '-35 days')
                    ORDER BY sampled_at DESC
                ''', (project_id,))
                history = [dict(row) for row in cursor.fetchall()]

            # Find stars from 7d, 14d, 21d and 30d ago
            stars_7d_ago = None
            stars_14d_ago = None
            stars_21d_ago = None
            stars_30d_ago = None

            now = datetime.now(timezone.utc)
            for sample in history:
                sampled_at = sample.get('sampled_at')
                if not sampled_at:
                    continue
                sample_date = datetime.fromisoformat(sampled_at.replace('Z', '+00:00')).date()
                days_ago = (now.date() - sample_date).days

                try:
                    sample_stars = int(sample['stars']) if sample.get('stars') is not None else None
                except (ValueError, TypeError):
                    sample_stars = None
                if 6 <= days_ago <= 8 and stars_7d_ago is None and sample_stars is not None:
                    stars_7d_ago = sample_stars
                if 13 <= days_ago <= 15 and stars_14d_ago is None and sample_stars is not None:
                    stars_14d_ago = sample_stars
                if 20 <= days_ago <= 22 and stars_21d_ago is None and sample_stars is not None:
                    stars_21d_ago = sample_stars
                if 28 <= days_ago <= 32 and stars_30d_ago is None and sample_stars is not None:
                    stars_30d_ago = sample_stars

            # Calculate scores (acceleration-aware when 14d+ data exists)
            # When no usable history exists, fall back to an events-derived
            # recent star rate (daily-budgeted) instead of the flat 0.5.
            velocity_source = 'history' if (stars_7d_ago is not None or stars_30d_ago is not None) else 'fallback'
            event_rate = None
            if (velocity_source == 'fallback'
                    and self._event_rates_done < self.config.get_event_rate_max_per_day()):
                event_rate = self._fetch_recent_star_rate(project_id)
                self._event_rates_done += 1
            if event_rate and event_rate['stars_gained'] > 0:
                pseudo_past_7d = max(current_stars - int(round(event_rate['rate'] * 7)), 0)
                velocity_score = self.scoring.calculate_star_velocity(current_stars, pseudo_past_7d)
                velocity_source = 'events'
            else:
                # 保留零增速的 recent_star_rate 记录（区分"已查无增长"与"未查"），
                # 只门控 velocity_source 标签（review 低-2）
                velocity_score = self.scoring.calculate_star_velocity(
                    current_stars, stars_7d_ago, stars_14d_ago, stars_21d_ago, stars_30d_ago
                )
            # Estimate commit frequency from last push date (pushed_at -> last_commit_at)
            last_commit = proj['last_commit_at'] or ''
            commit_frequency = 1.0
            if last_commit:
                try:
                    last_dt = datetime.fromisoformat(last_commit.replace('Z', '+00:00'))
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=timezone.utc)
                    days = (datetime.now(timezone.utc) - last_dt).days
                    days = max(days, 0)
                    if days <= 7:
                        commit_frequency = 5.0
                    elif days <= 30:
                        commit_frequency = 2.0
                    else:
                        commit_frequency = 0.5
                except (ValueError, TypeError):
                    pass
            try:
                open_issues = int(proj['open_issues']) if proj['open_issues'] is not None else 0
            except (ValueError, TypeError):
                open_issues = 0
            fresh_facts = self._structure_within_budget(project_id, conn)
            structure = None
            if fresh_facts:
                structure = fresh_facts
            elif proj['structure_json']:
                try:
                    structure = json.loads(proj['structure_json'])
                except (json.JSONDecodeError, TypeError):
                    structure = None
            activity_score = self.scoring.calculate_activity_index(
                open_issues, commit_frequency,
                has_tests=(structure or {}).get('has_tests'),
                has_ci=(structure or {}).get('has_ci')
            )
            contributor_count = proj['contributor_count']
            # contributor_count semantics: NULL = never tried; >= 0 = real count;
            # negative = consecutive fetch failures (-3 and below = fused, no retry).
            # Budgeted like the other collectors (review: this was the only
            # unbudgeted API consumer; failing repos retried every run forever).
            if contributor_count is None or (contributor_count < 0 and contributor_count > -3):
                if self._contributors_done < self.config.get_contributors_max_per_day():
                    self._contributors_done += 1
                    fetched = self._fetch_weekly_contributors(project_id)
                    if fetched is not None:
                        contributor_count = fetched
                    else:
                        contributor_count = (contributor_count or 0) - 1
                    conn.execute(
                        'UPDATE projects SET contributor_count = ? WHERE id = ?',
                        (contributor_count, project_id)
                    )
            novelty_score = self.scoring.calculate_novelty(
                proj['first_commit_at'] or proj['created_at'],
                contributor_count if contributor_count is not None and contributor_count >= 0 else 1
            )
            issue_health = (structure or {}).get('issue_health')
            buzz_score = self.scoring.calculate_buzz(issue_health)
            buzz_source = 'real' if issue_health else 'fallback'

            result = self.scoring.calculate_overall(
                velocity_score, activity_score, buzz_score, novelty_score
            )

            # Store result
            now_iso = datetime.now(timezone.utc).isoformat()
            conn.execute('''
                INSERT INTO early_burst_signals (
                    project_id, calculated_at,
                    star_velocity_score, activity_index_score,
                    community_buzz_score, novelty_score,
                    overall_score, is_early_burst, signals_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                project_id, now_iso,
                result['star_velocity_score'],
                result['activity_index_score'],
                result['community_buzz_score'],
                result['novelty_score'],
                result['overall_score'],
                result['is_early_burst'],
                json.dumps({
                    'stars_7d_ago': stars_7d_ago,
                    'stars_14d_ago': stars_14d_ago,
                    'stars_21d_ago': stars_21d_ago,
                    'stars_30d_ago': stars_30d_ago,
                    'current_stars': current_stars,
                    'buzz_source': buzz_source,
                    'velocity_source': velocity_source,
                    'recent_star_rate': event_rate,
                    'synthetic_history': bool(
                        history and proj['first_seen_at']
                        and min(h['sampled_at'] for h in history) < str(proj['first_seen_at'])[:10]
                    ),
                })
            ))
            if should_close:
                conn.commit()

        finally:
            if should_close:
                conn.close()

    def discover_topics(self) -> List[Dict]:
        """Discover from GitHub topics."""
        results = []
        topics = [str(t) for t in self.config.get_github_topics() if t]
        languages = self.config.load().get('sources', {}).get('github', {}).get('languages', [])
        if not isinstance(languages, list):
            languages = []
        languages = [str(l) for l in languages if l]

        print(f"Discovering from {len(topics)} topics x {len(languages)} languages...")

        for topic in topics:
            for lang in languages:
                # Quote topic/lang if they contain spaces for valid GitHub search syntax
                safe_topic = f'"{topic}"' if ' ' in topic else topic
                safe_lang = f'"{lang}"' if ' ' in lang else lang
                cutoff = (datetime.now(timezone.utc) - timedelta(days=self.created_within_days)).strftime('%Y-%m-%d')
                query = f"topic:{safe_topic} language:{safe_lang} stars:{self.star_min}..{self.star_max} created:>{cutoff}"
                url = "https://api.github.com/search/repositories"

                try:
                    data = self._github_request(url, {"q": query, "sort": "updated", "per_page": 30}, is_search=True)

                    if not isinstance(data, dict):
                        print(f"  Unexpected search response type: {type(data)}")
                        continue

                    items = data.get('items')
                    if not isinstance(items, list):
                        print(f"  Unexpected items type: {type(items)}")
                        continue
                    for repo in items:
                        if not isinstance(repo, dict):
                            continue
                        skip, reason = self._should_skip_repo(repo)
                        if not skip:
                            results.append({
                                'repo': repo,
                                'source': 'github_topic',
                                'signal': f"{topic}/{lang}"
                            })
                        else:
                            print(f"  Skip ({reason}): {repo.get('full_name', 'unknown')}")

                except GitHubAPIError as e:
                    print(f"  Error searching {topic}/{lang}: {e}")
                    continue

        return results

    def discover_ecosystems(self) -> List[Dict]:
        """Discover from ecosystem organizations."""
        results = []
        ecosystems = [str(e) for e in self.config.get_ecosystems() if e]

        print(f"Discovering from {len(ecosystems)} ecosystems...")

        for org in ecosystems:
            page = 1
            while page <= 5:
                url = f"https://api.github.com/orgs/{quote(org, safe='')}/repos"
                params = {"per_page": 100, "page": page, "sort": "updated"}

                try:
                    repos = self._github_request(url, params)

                    if not repos:
                        break

                    if not isinstance(repos, list):
                        print(f"  Unexpected response type from {org}: {type(repos)}")
                        break

                    for repo in repos:
                        if not isinstance(repo, dict):
                            continue
                        try:
                            stars = int(repo.get('stargazers_count') or 0)
                        except (ValueError, TypeError):
                            stars = 0
                        if stars < self.star_min or stars > self.star_max:
                            continue

                        skip, reason = self._should_skip_repo(repo)
                        if not skip:
                            results.append({
                                'repo': repo,
                                'source': 'ecosystem',
                                'signal': org
                            })

                    page += 1

                except GitHubAPIError as e:
                    print(f"  Error fetching {org}: {e}")
                    break

        return results

    def discover_trending(self) -> List[Dict]:
        """Discover from GitHub Trending pages (HTML parsing)."""
        cfg = self.config.load()
        trending_cfg = cfg.get('sources', {}).get('trending', {})
        languages = trending_cfg.get('languages', [])
        if not isinstance(languages, list):
            languages = []
        languages = [str(l) for l in languages if l]
        periods = trending_cfg.get('periods', ['daily', 'weekly'])
        if not isinstance(periods, list):
            periods = ['daily', 'weekly']
        periods = [str(p) for p in periods if p]

        # GitHub non-repo path prefixes to filter out navigation links
        _NON_REPO_PREFIXES = {
            "features", "marketplace", "login", "logout", "settings", "explore",
            "notifications", "issues", "pulls", "sponsors", "about", "pricing",
            "enterprise", "topics", "collections", "events", "apps", "contact",
            "security", "organizations", "new", "codespaces", "copilot", "orgs", "users",
            "trending",
        }
        # Common web asset extensions that are never repositories
        _ASSET_EXTENSIONS = {
            '.js', '.css', '.png', '.jpg', '.jpeg', '.svg', '.ico',
            '.woff', '.woff2', '.ttf', '.eot', '.json', '.xml', '.map',
        }

        results = []
        for lang in languages:
            for period in periods:
                url = f"https://github.com/trending/{quote(lang, safe='')}?since={period}"
                try:
                    r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=15)
                    r.raise_for_status()
                    raw = re.findall(
                        r'href\s*=\s*[\'"]/([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)[\'"]', r.text
                    )
                    seen: Set[str] = set()
                    repo_names: List[str] = []
                    for full_name in raw:
                        full_name = full_name.lower()
                        if full_name in seen:
                            continue
                        seen.add(full_name)
                        owner = full_name.split("/")[0]
                        if owner in _NON_REPO_PREFIXES:
                            continue
                        if any(full_name.endswith(ext) for ext in _ASSET_EXTENSIONS):
                            continue
                        repo_names.append(full_name)
                        if len(repo_names) >= 25:
                            break

                    if not repo_names:
                        print(
                            f"  WARN: trending {lang}/{period} parsed 0 projects, "
                            "HTML structure may have changed"
                        )
                        continue

                    for full_name in repo_names:
                        api_url = f"https://api.github.com/repos/{full_name}"
                        try:
                            repo = self._github_request(api_url)
                            if not repo:
                                continue
                            skip, reason = self._should_skip_repo(repo)
                            if not skip:
                                results.append({
                                    'repo': repo,
                                    'source': 'trending',
                                    'signal': f"{lang}/{period}",
                                })
                        except GitHubAPIError:
                            pass
                except requests.exceptions.RequestException as e:
                    print(f"  trending_error {lang}/{period}: {e}")
                time.sleep(1)

        return results

    def run(self, dry_run: bool = False):
        """Execute full discovery process."""
        print("=== Stage 1: Discover ===")
        print(f"Star range: {self.star_min} - {self.star_max}")
        print(f"Dry run: {dry_run}")
        print()

        all_results = []

        # Source 1: Topics
        print("Source 1: GitHub Topics...")
        all_results.extend(self.discover_topics())
        print(f"  Found: {len(all_results)} projects")

        # Source 2: Ecosystems
        print("Source 2: Ecosystem Organizations...")
        eco_results = self.discover_ecosystems()
        all_results.extend(eco_results)
        print(f"  Found: {len(eco_results)} projects")

        # Source 3: Trending
        print("Source 3: GitHub Trending...")
        trending_results = self.discover_trending()
        all_results.extend(trending_results)
        print(f"  Found: {len(trending_results)} projects")

        # Deduplicate (case-insensitive to avoid owner/repo casing mismatches)
        seen: Set[str] = set()
        unique_results = []
        for item in all_results:
            pid = (item.get('repo') or {}).get('full_name')
            if pid:
                pid_lower = pid.lower()
                if pid_lower not in seen:
                    seen.add(pid_lower)
                    unique_results.append(item)

        print(f"\nTotal unique projects: {len(unique_results)}")

        if dry_run:
            print("\nDry run - not writing to database")
            for item in unique_results[:10]:
                print(f"  {(item.get('repo') or {}).get('full_name', 'unknown')} ({item['source']})")
            return

        # Store results
        print("\nStoring projects...")
        stored_count = 0
        conn = self.db.get_conn()
        try:
            for item in unique_results:
                try:
                    project_id = self._upsert_project(
                        item['repo'], item['source'], item['signal'],
                        conn=conn
                    )
                    stored_count += 1
                    new_stars = (item.get('repo') or {}).get('stargazers_count') or 0
                    self._sample_star_count(
                        project_id,
                        new_stars,
                        conn=conn
                    )
                    self._calculate_and_store_burst_score(project_id, conn=conn)
                except Exception as e:
                    repo_name = (item.get('repo') or {}).get('full_name', 'unknown')
                    print(f"  Error storing {repo_name}: {e}")
            conn.commit()
        finally:
            conn.close()

        print(f"\nStored {stored_count} projects")

        # Sample star counts for existing active projects
        # Newest-first: the events-rate budget serves recent discoveries before
        # long-tail legacy projects (review M1).
        print("\nSampling star history for existing projects...")
        conn = self.db.get_conn()
        try:
            active_projects = conn.execute(
                "SELECT id, stars FROM projects WHERE status IN ('scheduled', 'active') "
                "ORDER BY first_seen_at DESC"
            ).fetchall()

            sampled = 0
            for proj in active_projects:
                try:
                    try:
                        proj_stars = int(proj['stars']) if proj['stars'] is not None else 0
                    except (ValueError, TypeError):
                        proj_stars = 0
                    self._sample_star_count(proj['id'], proj_stars, conn=conn)
                    self._calculate_and_store_burst_score(proj['id'], conn=conn)
                    sampled += 1
                except Exception as e:
                    print(f"  Error sampling {proj['id']}: {e}")
            conn.commit()

            print(f"  Sampled {sampled}/{len(active_projects)} existing projects")
        finally:
            conn.close()


def main():
    parser = argparse.ArgumentParser(description="Discover AI projects")
    parser.add_argument('--dry-run', action='store_true', help="Don't write to database")
    args = parser.parse_args()

    config = ConfigLoader()
    db = Database()

    stage = DiscoverStage(config, db)
    stage.run(dry_run=args.dry_run)


if __name__ == '__main__':
    main()
